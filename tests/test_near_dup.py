from __future__ import annotations

import pytest

from adjacency.contracts import InventoryItem
from adjacency.near_dup import (
    NearDupCluster,
    minhash_signature,
    minhash_similarity,
    perceptual_hash_from_luma,
)


def item(item_id: str, text: str) -> InventoryItem:
    return InventoryItem(item_id=item_id, text=text)


def test_phash_is_stable_and_changes_when_the_pattern_changes():
    vertical = [[255 if x < 4 else 0 for x in range(8)] for _ in range(8)]
    horizontal = [[255 if y < 4 else 0 for _ in range(8)] for y in range(8)]

    first = perceptual_hash_from_luma(vertical)
    assert first == perceptual_hash_from_luma(vertical)
    assert first != perceptual_hash_from_luma(horizontal)


def test_minhash_handles_empty_short_and_near_duplicate_text():
    assert minhash_signature("") == ()
    assert len(minhash_signature("short text", permutations=8)) == 8
    left = minhash_signature(
        "launch vehicles reach orbit after careful testing at the coastal range"
    )
    right = minhash_signature(
        "launch vehicles reach orbit after careful testing at the coastal range today"
    )
    assert minhash_similarity(left, right) >= 0.8
    assert minhash_similarity((), right) == 0.0


def test_cluster_combines_phash_and_minhash_matches_and_can_keep_singletons():
    items = [
        item("image-a", "alpha unique"),
        item("image-b", "beta distinct"),
        item("image-c", "gamma separate"),
        item("text-a", "launch vehicles reach orbit after careful testing at the coastal range"),
        item(
            "text-b",
            "launch vehicles reach orbit after careful testing at the coastal range today",
        ),
        item("single", "a wholly unrelated sentence about gardening"),
    ]
    clusterer = NearDupCluster(phash_distance=1, text_similarity=0.8)

    duplicate_groups = clusterer.cluster(
        items,
        {"image-a": (0b0000,), "image-b": (0b0001,), "image-c": (0b0001,)},
    )
    assert [group.item_ids for group in duplicate_groups] == [
        ("image-a", "image-b", "image-c"),
        ("text-a", "text-b"),
    ]
    all_groups = clusterer.cluster(
        items,
        {"image-a": (0b0000,), "image-b": (0b0001,), "image-c": (0b0001,)},
        include_singletons=True,
    )
    assert all_groups[-1].item_ids == ("single",)


def test_invalid_hash_inputs_and_cluster_configuration_fail_closed():
    with pytest.raises(ValueError, match="hash_size"):
        perceptual_hash_from_luma([[0]], hash_size=1)
    with pytest.raises(ValueError, match="square matrix"):
        perceptual_hash_from_luma([[0, 0], [0]], hash_size=2)
    with pytest.raises(ValueError, match="luma values"):
        perceptual_hash_from_luma([[0, 0], [0, 256]], hash_size=2)
    with pytest.raises(ValueError, match="positive"):
        minhash_signature("text", permutations=0)
    with pytest.raises(ValueError, match="same length"):
        minhash_similarity((1,), (1, 2))
    with pytest.raises(ValueError, match="negative"):
        NearDupCluster(phash_distance=-1)
    with pytest.raises(ValueError, match="between 0 and 1"):
        NearDupCluster(text_similarity=1.1)
    with pytest.raises(ValueError, match="positive"):
        NearDupCluster(permutations=0)


def test_duplicate_items_and_unknown_image_hashes_are_rejected():
    repeated = item("same", "text")
    clusterer = NearDupCluster()

    with pytest.raises(ValueError, match="duplicate inventory"):
        clusterer.cluster([repeated, repeated])
    with pytest.raises(ValueError, match="unknown item"):
        clusterer.cluster([repeated], {"other": (1,)})
