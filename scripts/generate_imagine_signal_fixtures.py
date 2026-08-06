#!/usr/bin/env python3
"""Verify or explicitly create the three synthetic ImagineSignal image fixtures.

The safe default is verification. ``--write`` creates missing fixtures through the
project fixture API, but immutable conflicting records still fail closed. This script
uses no network client, API key, provider SDK, or consumer subscription. Its output is
local synthetic evidence and makes no claim about current xAI model behavior.
"""

from __future__ import annotations

import argparse
import binascii
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from adjacency.imagine_signal.adapters.fixture_blobs import (
    BinaryFixtureStore,
    metadata_sha256,
)
from adjacency.imagine_signal.imagine_client import GENERATE_SURFACE, FixtureImagineClient
from adjacency.imagine_signal.ports import (
    CostMeasurement,
    ImageGenerationRequest,
    ResponseOrigin,
    TransportImage,
)

WIDTH = 192
HEIGHT = 192
GENERATOR_ID = "imagine-signal-orbit-raster-v1"
MODEL = "grok-imagine-image-2026-03-02"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "imagine_signal"

GLYPHS = {
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
}


@dataclass(frozen=True, slots=True)
class FixtureSpec:
    level: str
    prompt: str
    background: tuple[int, int, int]
    request_sha256: str
    response_sha256: str
    media_sha256: str


SPECS = (
    FixtureSpec(
        level="neutral",
        prompt=(
            "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and "
            "text. Use the approved neutral background tone."
        ),
        background=(154, 158, 166),
        request_sha256="670ebcb5133096c696897fccf3f681219e81cc559837d79b037d4c3f5744597c",
        response_sha256="963a8ec5b14b0d2879ccd2d4d82666147e33c15d4703b044312fd4a67065e79f",
        media_sha256="f760c2932b70e2f65196ec13359f07eef6f5a916fa5684f499abb12b18916400",
    ),
    FixtureSpec(
        level="warm",
        prompt=(
            "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and "
            "text. Change only background_tone. Set the background_tone to warm."
        ),
        background=(218, 142, 96),
        request_sha256="9be071d08ee9c03539f88208b812afd68a6af07eb9ecae83408b4c6fb3a24779",
        response_sha256="9b38a065d3e7f4681c227cbf752dc640aa86a72216da4a86fc4294da344bfd01",
        media_sha256="300aeddfd6f32a8153015ab418004eba458a0511fdfa45eab9331f5de062c809",
    ),
    FixtureSpec(
        level="cool",
        prompt=(
            "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and "
            "text. Change only background_tone. Set the background_tone to cool."
        ),
        background=(91, 146, 214),
        request_sha256="7aff99de5814653328c85d0c40903f9a620700f61c2522e58d88b00bd289d4c6",
        response_sha256="c10afae538709d688aa63a98ca3a90b07ddfa97af7ea9c76ccdaed90e50944f5",
        media_sha256="c0c77a34d6ac5bfe4bbb0ac4a1ebfb0831281608da103911ad7642e84f70ebb9",
    ),
)


class FixtureVerificationError(RuntimeError):
    """Generated and committed fixture evidence differ."""


def request_for(spec: FixtureSpec) -> ImageGenerationRequest:
    return ImageGenerationRequest(
        schema_version="1.0",
        model=MODEL,
        prompt=spec.prompt,
        n=1,
        aspect_ratio="1:1",
        resolution="1k",
        data_classification="synthetic",
    )


def response_metadata(spec: FixtureSpec) -> dict[str, object]:
    return {
        "state": "COMPLETED",
        "response_origin": "SYNTHETIC_FIXTURE",
        "generator_id": GENERATOR_ID,
        "provider_request_id": f"synthetic-orbit-{spec.level}-v1",
        "provider_model_requested": MODEL,
        "provider_model_resolved": "synthetic-fixture-renderer-v1",
        "moderation_respected": True,
        "cost": {"status": "KNOWN", "ticks": 0},
        "budget_status": "WITHIN_LIMIT",
        "latency_ms": 0,
        "error_code": None,
    }


def render(background: tuple[int, int, int]) -> bytes:
    """Render fixed foreground pixels over exactly one selected background color."""

    pixels = bytearray(background * (WIDTH * HEIGHT))

    def point(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            offset = 3 * (y * WIDTH + x)
            pixels[offset : offset + 3] = bytes(color)

    def rectangle(
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: tuple[int, int, int],
    ) -> None:
        for y in range(y0, y1):
            for x in range(x0, x1):
                point(x, y, color)

    dark = (24, 29, 38)
    bottle = (235, 240, 244)
    highlight = (255, 255, 255)
    label = (40, 52, 75)
    orbit = (99, 218, 255)

    rectangle(80, 13, 112, 25, dark)
    rectangle(83, 25, 109, 47, bottle)
    rectangle(76, 47, 116, 55, bottle)
    rectangle(70, 55, 122, 67, bottle)
    rectangle(66, 67, 126, 164, bottle)
    rectangle(70, 71, 75, 158, highlight)
    rectangle(66, 160, 126, 166, dark)
    rectangle(70, 91, 122, 135, label)

    center_x, center_y = 96, 107
    for y in range(center_y - 12, center_y + 13):
        for x in range(center_x - 12, center_x + 13):
            distance = (x - center_x) ** 2 + (y - center_y) ** 2
            if 65 <= distance <= 120:
                point(x, y, orbit)

    cursor_x = 80
    for character in "ORBIT":
        for row, pattern in enumerate(GLYPHS[character]):
            for column, enabled in enumerate(pattern):
                if enabled == "1":
                    point(cursor_x + column, 119 + row, highlight)
        cursor_x += 7

    def chunk(name: bytes, payload: bytes) -> bytes:
        checksum = binascii.crc32(name + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    scanlines = b"".join(
        b"\x00" + bytes(pixels[row * WIDTH * 3 : (row + 1) * WIDTH * 3]) for row in range(HEIGHT)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + chunk(b"IEND", b"")
    )


def verify_expected_hashes(store: BinaryFixtureStore, spec: FixtureSpec, media: bytes) -> None:
    request = request_for(spec)
    descriptor = store.asset_store.validate(
        media,
        declared_content_type="image/png",
        declared_width=WIDTH,
        declared_height=HEIGHT,
    )
    request_hash = store.request_hash(GENERATE_SURFACE, request)
    response_hash = metadata_sha256(
        {
            "assets": [descriptor.model_dump(mode="json")],
            "metadata": response_metadata(spec),
        }
    )
    actual = (request_hash, response_hash, descriptor.media_sha256)
    expected = (spec.request_sha256, spec.response_sha256, spec.media_sha256)
    if actual != expected:
        raise FixtureVerificationError(
            f"generated hashes changed for {spec.level}: expected {expected}, got {actual}"
        )


def write_missing(store: BinaryFixtureStore) -> None:
    for spec in SPECS:
        media = render(spec.background)
        verify_expected_hashes(store, spec, media)
        store.record(
            surface=GENERATE_SURFACE,
            request=request_for(spec),
            response_metadata=response_metadata(spec),
            images=(
                TransportImage(
                    media_bytes=media,
                    declared_content_type="image/png",
                    declared_width=WIDTH,
                    declared_height=HEIGHT,
                    expected_sha256=spec.media_sha256,
                ),
            ),
        )


def verify_committed(store: BinaryFixtureStore) -> list[dict[str, object]]:
    client = FixtureImagineClient(store)
    proof = []
    for spec in SPECS:
        media = render(spec.background)
        verify_expected_hashes(store, spec, media)
        result = client.generate(request_for(spec))
        if result.response_origin != ResponseOrigin.SYNTHETIC_FIXTURE:
            raise FixtureVerificationError(f"fixture origin changed for {spec.level}")
        if result.generator_id != GENERATOR_ID:
            raise FixtureVerificationError(f"fixture generator changed for {spec.level}")
        if result.cost != CostMeasurement.known(0):
            raise FixtureVerificationError(f"fixture cost is not exact local zero for {spec.level}")
        image = result.images[0]
        if (
            result.request_sha256 != spec.request_sha256
            or result.response_sha256 != spec.response_sha256
            or image.media_sha256 != spec.media_sha256
        ):
            raise FixtureVerificationError(f"committed hashes changed for {spec.level}")
        if Path(image.blob_path).read_bytes() != media:
            raise FixtureVerificationError(f"committed bytes changed for {spec.level}")
        proof.append(
            {
                "level": spec.level,
                "request_sha256": result.request_sha256,
                "response_sha256": result.response_sha256,
                "media_sha256": image.media_sha256,
                "response_origin": result.response_origin,
                "generator_id": result.generator_id,
                "cost_ticks": result.cost.ticks,
            }
        )
    return proof


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="verify committed fixtures without writing, the default",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="create missing exact fixtures, then verify them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = BinaryFixtureStore(FIXTURE_ROOT)
    if args.write:
        write_missing(store)
    proof = verify_committed(store)
    print(
        json.dumps(
            {
                "mode": "write-and-verify" if args.write else "verify-only",
                "fixture_root": str(FIXTURE_ROOT),
                "generator_id": GENERATOR_ID,
                "network_used": False,
                "provider_call_used": False,
                "fixtures": proof,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
