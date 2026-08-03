"""Deterministic near-duplicate clustering from pHash and text MinHash."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from statistics import median

from adjacency.contracts import InventoryItem, normalize

_TOKEN = re.compile(r"\w+", re.UNICODE)


def perceptual_hash_from_luma(
    pixels: Sequence[Sequence[int]],
    *,
    hash_size: int = 8,
) -> int:
    """Compute a pHash from a square grayscale matrix.

    Image decoding and resizing stay outside this pure function. Corpus creation
    supplies a fixed-size luma matrix, and the frozen corpus can store the returned
    integer for offline replay.
    """

    size = len(pixels)
    if hash_size < 2:
        raise ValueError("hash_size must be at least 2")
    if size < hash_size or any(len(row) != size for row in pixels):
        raise ValueError("pixels must be a square matrix at least as large as hash_size")
    if any(value < 0 or value > 255 for row in pixels for value in row):
        raise ValueError("luma values must be between 0 and 255")

    coefficients = []
    angle_scale = math.pi / (2 * size)
    frequency_scales = [
        math.sqrt(1 / size) if frequency == 0 else math.sqrt(2 / size)
        for frequency in range(hash_size)
    ]
    for vertical_frequency in range(hash_size):
        for horizontal_frequency in range(hash_size):
            coefficient = 0.0
            for y, row in enumerate(pixels):
                vertical = math.cos((2 * y + 1) * vertical_frequency * angle_scale)
                for x, value in enumerate(row):
                    horizontal = math.cos((2 * x + 1) * horizontal_frequency * angle_scale)
                    coefficient += value * horizontal * vertical
            coefficients.append(
                coefficient
                * frequency_scales[vertical_frequency]
                * frequency_scales[horizontal_frequency]
            )

    threshold = median(coefficients[1:])
    result = 0
    for coefficient in coefficients:
        result = (result << 1) | int(coefficient >= threshold)
    return result


def minhash_signature(
    text: str,
    *,
    permutations: int = 64,
    shingle_size: int = 3,
) -> tuple[int, ...]:
    if permutations < 1 or shingle_size < 1:
        raise ValueError("permutations and shingle_size must be positive")
    tokens = _TOKEN.findall(normalize(text).casefold())
    if not tokens:
        return ()
    if len(tokens) < shingle_size:
        shingles = {" ".join(tokens)}
    else:
        shingles = {
            " ".join(tokens[index : index + shingle_size])
            for index in range(len(tokens) - shingle_size + 1)
        }
    return tuple(
        min(
            int.from_bytes(
                hashlib.sha256(f"{seed}\0{shingle}".encode()).digest()[:8],
                "big",
            )
            for shingle in shingles
        )
        for seed in range(permutations)
    )


def minhash_similarity(left: Sequence[int], right: Sequence[int]) -> float:
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        raise ValueError("MinHash signatures must have the same length")
    return sum(a == b for a, b in zip(left, right, strict=True)) / len(left)


@dataclass(frozen=True, slots=True)
class NearDupGroup:
    cluster_id: str
    item_ids: tuple[str, ...]


class NearDupCluster:
    """Build connected components when either duplicate signal is strong."""

    def __init__(
        self,
        *,
        phash_distance: int = 6,
        text_similarity: float = 0.8,
        permutations: int = 64,
        shingle_size: int = 3,
    ):
        if phash_distance < 0:
            raise ValueError("phash_distance cannot be negative")
        if not 0.0 <= text_similarity <= 1.0:
            raise ValueError("text_similarity must be between 0 and 1")
        if permutations < 1 or shingle_size < 1:
            raise ValueError("permutations and shingle_size must be positive")
        self.phash_distance = phash_distance
        self.text_similarity = text_similarity
        self.permutations = permutations
        self.shingle_size = shingle_size

    def cluster(
        self,
        items: Sequence[InventoryItem],
        image_hashes: Mapping[str, Sequence[int]] | None = None,
        *,
        include_singletons: bool = False,
    ) -> tuple[NearDupGroup, ...]:
        ordered_items = tuple(items)
        item_ids = [item.item_id for item in ordered_items]
        duplicate_ids = sorted({item_id for item_id in item_ids if item_ids.count(item_id) > 1})
        if duplicate_ids:
            raise ValueError(f"duplicate inventory item ids: {duplicate_ids}")
        hashes = image_hashes or {}
        unknown_hash_ids = sorted(set(hashes) - set(item_ids))
        if unknown_hash_ids:
            raise ValueError(f"image hashes reference unknown item ids: {unknown_hash_ids}")

        signatures = {
            item.item_id: minhash_signature(
                item.text,
                permutations=self.permutations,
                shingle_size=self.shingle_size,
            )
            for item in ordered_items
        }
        parents = {item_id: item_id for item_id in item_ids}

        def find(item_id: str) -> str:
            while parents[item_id] != item_id:
                parents[item_id] = parents[parents[item_id]]
                item_id = parents[item_id]
            return item_id

        def union(left_id: str, right_id: str) -> None:
            left_root = find(left_id)
            right_root = find(right_id)
            if left_root != right_root:
                parents[right_root] = left_root

        for left, right in combinations(ordered_items, 2):
            left_hashes = hashes.get(left.item_id, ())
            right_hashes = hashes.get(right.item_id, ())
            image_match = any(
                (left_hash ^ right_hash).bit_count() <= self.phash_distance
                for left_hash in left_hashes
                for right_hash in right_hashes
            )
            text_match = (
                minhash_similarity(signatures[left.item_id], signatures[right.item_id])
                >= self.text_similarity
            )
            if image_match or text_match:
                union(left.item_id, right.item_id)

        grouped: dict[str, list[str]] = {}
        for item_id in item_ids:
            grouped.setdefault(find(item_id), []).append(item_id)

        groups = []
        for members in grouped.values():
            if len(members) == 1 and not include_singletons:
                continue
            member_ids = tuple(members)
            cluster_id = hashlib.sha256("\0".join(sorted(member_ids)).encode("utf-8")).hexdigest()[
                :16
            ]
            groups.append(NearDupGroup(cluster_id=cluster_id, item_ids=member_ids))
        return tuple(groups)
