#!/usr/bin/env python3
"""Discover X inventory, verify source posts, and freeze the local corpus."""

from __future__ import annotations

import json
from pathlib import Path

from adjacency.corpus import (
    CorpusFreezer,
    load_frozen_corpus,
    prune_unreferenced_media,
    save_frozen_corpus,
)
from adjacency.fixtures import FixtureStore
from adjacency.inventory import InventoryFetcher, InventorySearch, XSearchPost, XStatusResolver
from adjacency.xai import RecordedXAIClient

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "api"
DISCOVERY_ARTIFACT = ROOT / "artifacts" / "wednesday" / "inventory_discovery.json"
CORPUS_MANIFEST = ROOT / "corpus" / "frozen" / "manifest.json"

SEARCHES = (
    InventorySearch(
        label="clean_travel_nature",
        query=(
            "Original public posts from travel, nature, parks, weather, or space accounts. "
            "Prefer safe general-interest posts, and include attached photos when available."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="clean_science_technology",
        query=(
            "Original public posts about science, engineering, AI, or research announcements. "
            "Prefer posts with attached diagrams or photos and no violent content."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="neutral_public_health",
        query=(
            "Neutral public-health reporting about fentanyl, illicit drugs, overdose prevention, "
            "treatment, or law-enforcement seizures. Exclude posts offering drugs for sale."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="neutral_violence_reporting",
        query=(
            "Neutral news, public-safety, or violence-prevention reporting that mentions violence. "
            "Exclude content that celebrates harm and prefer non-graphic attached media."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="synthetic_media_policy",
        query=(
            "Public posts discussing deepfakes, synthetic media, or impersonation of public "
            "officials. Include reporting, policy guidance, and detection research."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="fictional_violence_context",
        query=(
            "Public posts discussing fictional action in films, television, games, or books. "
            "Prefer reviews and commentary that make the fictional context clear."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="drug_policy_news",
        query=(
            "Public posts about illegal drug sales, trafficking, enforcement, or drug policy. "
            "Prefer journalism and official reporting, not active sale offers."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="ambiguous_context",
        query=(
            "Public posts where words such as violence, drugs, synthetic, or deepfake appear in "
            "education, satire, prevention, or other non-promotional context."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=12,
    ),
    InventorySearch(
        label="clean_text_only",
        query=(
            "Original text-only public posts about weather, travel, science, daily life, or "
            "technology. Require no attached photo, video, GIF, link preview, or quoted post."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=20,
    ),
    InventorySearch(
        label="policy_text_only",
        query=(
            "Original text-only public posts about violence prevention, public health, drug "
            "policy, deepfakes, or synthetic media. Require no attached media, link, or quote."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=20,
    ),
    InventorySearch(
        label="news_text_only",
        query=(
            "Original text-only public commentary on current events, journalism, or public "
            "safety. Require no attached media, external link, link card, or quoted post."
        ),
        from_date="2026-01-01",
        to_date="2026-08-02",
        limit=20,
    ),
)


def main() -> None:
    fixture_store = FixtureStore(FIXTURE_ROOT)
    fetcher = InventoryFetcher(RecordedXAIClient(fixture_store))
    posts: list[tuple[str, XSearchPost]] = []
    fetch_records: list[dict[str, object]] = []
    fetch_failures: list[dict[str, str]] = []

    for search in SEARCHES:
        try:
            result = fetcher.fetch(search)
        except Exception as error:
            fetch_failures.append(
                {
                    "error": f"{type(error).__name__}: {error}",
                    "search_label": search.label,
                }
            )
            continue
        posts.extend((search.label, post) for post in result.posts)
        fetch_records.append(
            {
                "measurement": result.measurement.as_dict(),
                "posts": [post.model_dump(mode="json") for post in result.posts],
                "search": {
                    "from_date": search.from_date,
                    "label": search.label,
                    "limit": search.limit,
                    "query": search.query,
                    "to_date": search.to_date,
                },
            }
        )

    discovery_document = {
        "fetch_failures": fetch_failures,
        "fetch_records": fetch_records,
        "fetched_post_count_before_deduplication": len(posts),
    }
    resolver = XStatusResolver(fixture_store)
    if not fixture_store.record:
        corpus = _verify_committed_replay(discovery_document, resolver)
        removed_media: tuple[str, ...] = ()
    else:
        corpus = CorpusFreezer(ROOT, resolver).freeze(
            posts,
            frozen_on="2026-08-03",
            item_limit=50,
            media_target=18,
            max_media=20,
        )
        _write_json(DISCOVERY_ARTIFACT, discovery_document)
        save_frozen_corpus(CORPUS_MANIFEST, corpus)
        removed_media = prune_unreferenced_media(ROOT, corpus)

    print(
        json.dumps(
            {
                "corpus_hash": corpus.corpus_hash,
                "fetch_failure_count": len(fetch_failures),
                "fetched_post_count_before_deduplication": len(posts),
                "frozen_item_count": len(corpus.records),
                "media_item_count": sum(record.item.has_media for record in corpus.records),
                "metadata_or_media_skip_count": len(corpus.skipped_sources),
                "removed_unreferenced_media": list(removed_media),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _verify_committed_replay(
    discovery_document: dict[str, object],
    resolver: XStatusResolver,
):
    committed_discovery = json.loads(DISCOVERY_ARTIFACT.read_text(encoding="utf-8"))
    if _without_replay_latency(committed_discovery) != _without_replay_latency(discovery_document):
        raise RuntimeError("fixture replay changed the committed inventory discovery")

    corpus = load_frozen_corpus(CORPUS_MANIFEST, verify_media_root=ROOT)
    expected_media_paths = {
        str((ROOT / media.local_path).resolve())
        for record in corpus.records
        for media in record.media_records
    }
    actual_media_paths = {str(path.resolve()) for path in (ROOT / "corpus" / "media").glob("*.jpg")}
    if actual_media_paths != expected_media_paths:
        raise RuntimeError("local media files do not exactly match the frozen manifest")

    for record in corpus.records:
        details = resolver.resolve(record.source_url)
        expected_media_url = record.media_records[0].source_url if record.media_records else None
        if (
            details.text != record.item.text
            or details.author_handle != record.item.author_handle
            or details.created_at != record.item.created_at
            or details.media_url != expected_media_url
        ):
            raise RuntimeError(f"recorded source metadata changed for {record.source_url}")
    return corpus


def _without_replay_latency(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_replay_latency(item) for key, item in value.items() if key != "elapsed_ms"
        }
    if isinstance(value, list):
        return [_without_replay_latency(item) for item in value]
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
