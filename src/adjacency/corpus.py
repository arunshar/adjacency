"""Freeze verified X inventory and local media into a hashed corpus."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field

from adjacency.contracts import Frozen, InventoryItem, Media
from adjacency.inventory import XSearchPost, XStatusDetails, XStatusResolver
from adjacency.near_dup import perceptual_hash_from_luma


class FrozenMediaRecord(Frozen):
    media_id: str
    local_path: str
    source_url: str
    sha256: str = Field(min_length=64, max_length=64)
    perceptual_hash: int = Field(ge=0)


class FrozenCorpusRecord(Frozen):
    item: InventoryItem
    source_url: str
    source_query: str
    media_records: tuple[FrozenMediaRecord, ...] = ()


class SkippedSource(Frozen):
    source_url: str
    stage: Literal["metadata", "media"]
    error: str


class FrozenCorpus(Frozen):
    schema_version: Literal[1] = 1
    source: Literal["grok_x_search"] = "grok_x_search"
    frozen_on: str
    records: tuple[FrozenCorpusRecord, ...] = Field(min_length=1)
    skipped_sources: tuple[SkippedSource, ...] = ()

    @property
    def corpus_hash(self) -> str:
        blob = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @property
    def items(self) -> tuple[InventoryItem, ...]:
        return tuple(record.item for record in self.records)


@dataclass(frozen=True, slots=True)
class DownloadedImage:
    data: bytes
    width: int
    height: int
    perceptual_hash: int


ImageDownloader = Callable[[str], DownloadedImage]


class CorpusFreezeError(ValueError):
    """Raised when the requested frozen corpus cannot be built exactly."""


class CorpusFreezer:
    def __init__(
        self,
        root: Path | str,
        resolver: XStatusResolver,
        *,
        image_downloader: ImageDownloader | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.resolver = resolver
        self.image_downloader = image_downloader or download_and_normalize_image

    def freeze(
        self,
        posts: Sequence[tuple[str, XSearchPost]],
        *,
        frozen_on: str,
        item_limit: int = 50,
        media_target: int = 18,
        max_media: int = 20,
    ) -> FrozenCorpus:
        if not 1 <= media_target <= max_media <= item_limit:
            raise CorpusFreezeError("media bounds must fit inside the corpus size")

        resolved: list[tuple[str, XStatusDetails]] = []
        failures: list[SkippedSource] = []
        seen: set[str] = set()
        for query, post in posts:
            if post.source_url in seen:
                continue
            seen.add(post.source_url)
            try:
                details = self.resolver.resolve(post.source_url)
            except Exception as error:
                failures.append(
                    SkippedSource(
                        source_url=post.source_url,
                        stage="metadata",
                        error=f"{type(error).__name__}: {error}",
                    )
                )
            else:
                resolved.append((query, details))

        media_candidates = [entry for entry in resolved if entry[1].media_url]
        text_candidates = [entry for entry in resolved if not entry[1].media_url]
        media_records: list[FrozenCorpusRecord] = []
        selected_media_urls: set[str] = set()
        for query, details in media_candidates:
            if len(media_records) >= media_target:
                break
            try:
                record = self._record(query, details, include_media=True)
            except Exception as error:
                failures.append(
                    SkippedSource(
                        source_url=details.source_url,
                        stage="media",
                        error=f"{type(error).__name__}: {error}",
                    )
                )
            else:
                media_records.append(record)
                selected_media_urls.add(details.source_url)

        if len(media_records) < media_target:
            raise CorpusFreezeError(
                f"only {len(media_records)} media items could be frozen, need {media_target}"
            )

        selected = list(media_records)
        for query, details in text_candidates:
            if len(selected) >= item_limit:
                break
            selected.append(self._record(query, details, include_media=False))

        if len(selected) < item_limit:
            for query, details in media_candidates:
                if details.source_url in selected_media_urls:
                    continue
                if (
                    len(selected) >= item_limit
                    or sum(record.item.has_media for record in selected) >= max_media
                ):
                    break
                try:
                    record = self._record(query, details, include_media=True)
                except Exception as error:
                    failures.append(
                        SkippedSource(
                            source_url=details.source_url,
                            stage="media",
                            error=f"{type(error).__name__}: {error}",
                        )
                    )
                else:
                    selected.append(record)
                    selected_media_urls.add(details.source_url)

        if len(selected) != item_limit:
            raise CorpusFreezeError(
                f"only {len(selected)} verified items could be frozen, need {item_limit}"
            )
        selected.sort(key=lambda record: record.item.item_id)
        return FrozenCorpus(
            frozen_on=frozen_on,
            records=tuple(selected),
            skipped_sources=tuple(failures),
        )

    def _record(
        self,
        query: str,
        details: XStatusDetails,
        *,
        include_media: bool,
    ) -> FrozenCorpusRecord:
        status_id = details.source_url.rstrip("/").rsplit("/", 1)[-1]
        item_id = f"x-{status_id}"
        media: tuple[Media, ...] = ()
        media_records: tuple[FrozenMediaRecord, ...] = ()
        if include_media:
            if not details.media_url:
                raise CorpusFreezeError("media record has no source media URL")
            relative_path = Path("corpus") / "media" / f"{status_id}.jpg"
            target = self.root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file():
                downloaded = inspect_normalized_image(target.read_bytes())
            else:
                downloaded = self.image_downloader(details.media_url)
                target.write_bytes(downloaded.data)
            digest = hashlib.sha256(downloaded.data).hexdigest()
            media_id = f"{item_id}-media-1"
            media = (
                Media(
                    media_id=media_id,
                    kind="image",
                    width=downloaded.width,
                    height=downloaded.height,
                    local_path=str(relative_path),
                    url=details.media_url,
                ),
            )
            media_records = (
                FrozenMediaRecord(
                    media_id=media_id,
                    local_path=str(relative_path),
                    source_url=details.media_url,
                    sha256=digest,
                    perceptual_hash=downloaded.perceptual_hash,
                ),
            )
        item = InventoryItem(
            item_id=item_id,
            text=details.text,
            media=media,
            author_handle=details.author_handle,
            created_at=details.created_at,
        )
        return FrozenCorpusRecord(
            item=item,
            source_url=details.source_url,
            source_query=query,
            media_records=media_records,
        )


def save_frozen_corpus(path: Path | str, corpus: FrozenCorpus) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "corpus": corpus.model_dump(mode="json"),
        "corpus_hash": corpus.corpus_hash,
    }
    target.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_frozen_corpus(
    path: Path | str, *, verify_media_root: Path | str | None = None
) -> FrozenCorpus:
    source = Path(path)
    document = json.loads(source.read_text(encoding="utf-8"))
    corpus = FrozenCorpus.model_validate(document["corpus"])
    if document.get("corpus_hash") != corpus.corpus_hash:
        raise CorpusFreezeError("frozen corpus hash does not match its manifest")
    if verify_media_root is not None:
        root = Path(verify_media_root).resolve()
        for record in corpus.records:
            for media in record.media_records:
                candidate = (root / media.local_path).resolve()
                if not candidate.is_relative_to(root) or not candidate.is_file():
                    raise CorpusFreezeError(f"frozen media is missing: {media.local_path}")
                if hashlib.sha256(candidate.read_bytes()).hexdigest() != media.sha256:
                    raise CorpusFreezeError(f"frozen media hash changed: {media.local_path}")
    return corpus


def prune_unreferenced_media(root: Path | str, corpus: FrozenCorpus) -> tuple[str, ...]:
    corpus_root = Path(root).resolve()
    media_root = corpus_root / "corpus" / "media"
    expected = {
        (corpus_root / media.local_path).resolve()
        for record in corpus.records
        for media in record.media_records
    }
    removed: list[str] = []
    if not media_root.is_dir():
        return ()
    for candidate in media_root.glob("*.jpg"):
        resolved = candidate.resolve()
        if resolved not in expected:
            candidate.unlink()
            removed.append(str(candidate.relative_to(corpus_root)))
    return tuple(sorted(removed))


def download_and_normalize_image(url: str) -> DownloadedImage:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"pbs.twimg.com", "abs.twimg.com"}:
        raise CorpusFreezeError("refused media outside X image hosts")
    request = urllib.request.Request(url, headers={"User-Agent": "AdjacencyCorpus/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            raw = response.read(10_000_001)
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        raise CorpusFreezeError("media download failed") from error
    if len(raw) > 10_000_000:
        raise CorpusFreezeError("media download exceeded the size limit")

    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as image:
            image = image.convert("RGB")
            image.thumbnail((768, 768))
            output = io.BytesIO()
            image.save(output, format="JPEG", optimize=True, quality=85)
    except (OSError, ValueError) as error:
        raise CorpusFreezeError("downloaded media is not a supported image") from error
    return inspect_normalized_image(output.getvalue())


def inspect_normalized_image(data: bytes) -> DownloadedImage:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            image = image.convert("RGB")
            width, height = image.size
            grayscale = image.resize((8, 8)).convert("L")
            pixels = list(grayscale.getdata())
            luma = [pixels[index : index + 8] for index in range(0, 64, 8)]
            perceptual_hash = perceptual_hash_from_luma(luma)
    except (OSError, ValueError) as error:
        raise CorpusFreezeError("local media is not a supported image") from error
    return DownloadedImage(
        data=data,
        width=width,
        height=height,
        perceptual_hash=perceptual_hash,
    )
