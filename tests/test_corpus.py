from __future__ import annotations

import hashlib

import pytest

from adjacency.corpus import (
    CorpusFreezeError,
    CorpusFreezer,
    DownloadedImage,
    load_frozen_corpus,
    save_frozen_corpus,
)
from adjacency.inventory import XSearchPost, XStatusDetails

pytestmark = pytest.mark.integration


class StubResolver:
    def resolve(self, source_url: str) -> XStatusDetails:
        status_id = source_url.rsplit("/", 1)[-1]
        return XStatusDetails(
            source_url=source_url,
            text=f"Verified text {status_id}",
            author_handle="@example",
            created_at="August 1, 2026",
            media_url=(
                f"https://pbs.twimg.com/media/{status_id}.jpg" if status_id == "1" else None
            ),
            media_width=10 if status_id == "1" else None,
            media_height=10 if status_id == "1" else None,
        )


def fetched(status_id: str, *, media: bool) -> XSearchPost:
    return XSearchPost(
        source_url=f"https://x.com/example/status/{status_id}",
        text=f"Discovered {status_id}",
        author_handle="@example",
        created_at="2026-08-01",
        has_media=media,
    )


def test_freezer_writes_local_media_and_verifies_manifest_hashes(tmp_path):
    image = DownloadedImage(data=b"normalized-jpeg", width=8, height=6, perceptual_hash=7)
    freezer = CorpusFreezer(
        tmp_path,
        StubResolver(),
        image_downloader=lambda _url: image,
    )
    corpus = freezer.freeze(
        (("media", fetched("1", media=True)), ("text", fetched("2", media=False))),
        frozen_on="2026-08-03",
        item_limit=2,
        media_target=1,
        max_media=1,
    )
    manifest = tmp_path / "corpus" / "frozen" / "manifest.json"
    save_frozen_corpus(manifest, corpus)

    loaded = load_frozen_corpus(manifest, verify_media_root=tmp_path)

    assert loaded.corpus_hash == corpus.corpus_hash
    assert sum(item.has_media for item in loaded.items) == 1
    media_record = next(record for record in loaded.records if record.item.has_media)
    assert media_record.media_records[0].sha256 == hashlib.sha256(image.data).hexdigest()

    (tmp_path / media_record.media_records[0].local_path).write_bytes(b"changed")
    with pytest.raises(CorpusFreezeError, match="media hash changed"):
        load_frozen_corpus(manifest, verify_media_root=tmp_path)


def test_freezer_requires_the_requested_media_count(tmp_path):
    freezer = CorpusFreezer(
        tmp_path,
        StubResolver(),
        image_downloader=lambda _url: pytest.fail("no image expected"),
    )
    with pytest.raises(CorpusFreezeError, match="media items"):
        freezer.freeze(
            (("text", fetched("2", media=False)),),
            frozen_on="2026-08-03",
            item_limit=1,
            media_target=1,
            max_media=1,
        )
