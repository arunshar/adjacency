#!/usr/bin/env python3
"""One bounded xAI Imagine probe that reports the response *shape*, not its content.

Purpose: settle the UNVERIFIED provider field names before the hackathon so that
implementing ``extract_provider_response`` on Saturday is transcription rather
than discovery. Run this once on Friday, during preflight.

This script is deliberately outside the ImagineSignal package and is never
imported by it. It cannot be reached from the replay path, and the library keeps
its property of never looking up a credential.

Safety properties:

- Refuses to run without an explicit ``--confirm-authorized-call`` flag.
- Refuses to run without ``XAI_API_KEY`` already in the environment.
- Refuses a dollar cap above ``MAX_ALLOWED_USD``.
- Issues exactly one request. No retry, no fallback, no loop.
- Prints a structural summary by default. Base64 payloads, long strings, and
  anything credential-shaped are redacted before printing.
- Writes the raw response only when you pass an explicit ``--save`` path, and
  warns that the file may contain image bytes and a signed URL.

Usage:

    python hackathon/smoke_call.py --confirm-authorized-call --max-usd 0.05

    python hackathon/smoke_call.py --confirm-authorized-call --max-usd 0.05 \\
        --save ~/adjacency-preflight/first-response.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

XAI_API_BASE = "https://api.x.ai/v1"
GENERATIONS_PATH = "/images/generations"
MODEL_DISCOVERY_PATH = "/image-generation-models"
MODEL_STANDARD = "grok-imagine-image"
TICKS_PER_USD = 10_000_000_000

#: A preflight probe has no business spending more than this.
MAX_ALLOWED_USD = 0.25

#: Non-sensitive, synthetic, and deliberately dull. Not a real advertiser brief.
PROBE_PROMPT = "A plain ceramic mug centered on a neutral grey background, studio lighting"

REQUEST_TIMEOUT_SECONDS = 60

_LONG_STRING = 80
_SECRET_HINTS = ("key", "token", "secret", "authorization", "bearer")


def _redact(value: Any, *, key: str = "") -> Any:
    """Reduce a JSON value to its shape, hiding anything long or sensitive."""

    lowered = key.lower()
    if any(hint in lowered for hint in _SECRET_HINTS):
        return "<redacted:possible-credential>"
    if isinstance(value, dict):
        return {k: _redact(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        head = [_redact(v, key=key) for v in value[:2]]
        return head + [f"<...{len(value) - 2} more>"] if len(value) > 2 else head
    if isinstance(value, str):
        if len(value) > _LONG_STRING:
            return f"<str len={len(value)} likely base64 or URL>"
        return value
    return value


def _describe(value: Any, prefix: str = "") -> list[str]:
    """Produce a flat `path: type` listing so field names are easy to copy."""

    lines: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict | list):
                lines.append(f"{path}: {type(v).__name__}")
                lines.extend(_describe(v, path))
            else:
                shown = _redact(v, key=k)
                lines.append(f"{path}: {type(v).__name__} = {shown}")
    elif isinstance(value, list) and value:
        lines.extend(_describe(value[0], f"{prefix}[0]"))
    return lines


def _post(
    url: str, body: dict[str, Any], api_key: str
) -> tuple[dict[str, Any], int, dict[str, str]]:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - fixed https host, not user input
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310
        raw = json.loads(response.read().decode("utf-8"))
        headers = {k.lower(): v for k, v in response.headers.items()}
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return raw, elapsed_ms, headers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-authorized-call",
        action="store_true",
        help="Required. Confirms you have authorized exactly one paid provider call.",
    )
    parser.add_argument(
        "--max-usd",
        type=float,
        required=True,
        help=f"Dollar cap you are authorizing. Must not exceed {MAX_ALLOWED_USD}.",
    )
    parser.add_argument("--model", default=MODEL_STANDARD, help="Image model to probe.")
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Optional path for the raw response. May contain image bytes and a signed URL.",
    )
    args = parser.parse_args()

    if not args.confirm_authorized_call:
        print("Refusing: pass --confirm-authorized-call to authorize one paid call.")
        return 2
    if args.max_usd <= 0 or args.max_usd > MAX_ALLOWED_USD:
        print(f"Refusing: --max-usd must be between 0 and {MAX_ALLOWED_USD}.")
        return 2

    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        print("Refusing: XAI_API_KEY is not set. This script never reads a key file.")
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    if args.save is not None and args.save.expanduser().resolve().is_relative_to(repo_root):
        print(f"Refusing: --save must point outside the repository ({repo_root}).")
        return 2

    body = {"model": args.model, "prompt": PROBE_PROMPT, "n": 1}
    url = f"{XAI_API_BASE}{GENERATIONS_PATH}"

    print(f"Issuing exactly one request to {url}")
    print(f"Model: {args.model}   Cap authorized: ${args.max_usd:.4f}\n")

    try:
        raw, elapsed_ms, headers = _post(url, body, api_key)
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code}. Body follows, redacted:")
        try:
            print(json.dumps(_redact(json.loads(error.read().decode("utf-8"))), indent=2))
        except Exception:
            print("<unparseable error body>")
        return 1
    except urllib.error.URLError as error:
        print(f"Network failure before a response: {error.reason}")
        print("The request may or may not have been accepted. Check the console before retrying.")
        return 1

    ticks = None
    usage = raw.get("usage")
    if isinstance(usage, dict):
        candidate = usage.get("cost_in_usd_ticks")
        if isinstance(candidate, int):
            ticks = candidate

    print("=" * 72)
    print("RESPONSE FIELD MAP. Copy these paths into hackathon/COST_LEDGER.md")
    print("=" * 72)
    for line in _describe(raw):
        print(f"  {line}")

    print("\n" + "=" * 72)
    print("RESPONSE HEADERS, all of them")
    print("=" * 72)
    print("  Filtering these was a mistake in v1: the resolved model and the moderation")
    print("  disposition are not in the body, so if they exist at all they are here.")
    for name in sorted(headers):
        print(f"  {name}: {_redact(headers[name], key=name)}")

    print("\n" + "=" * 72)
    print("COST")
    print("=" * 72)
    print(f"  measured latency: {elapsed_ms} ms")
    if ticks is None:
        print("  cost_in_usd_ticks: NOT FOUND at usage.cost_in_usd_ticks")
        print("  Find the real path above and record it. Unknown cost blocks further calls.")
    else:
        print(f"  cost_in_usd_ticks: {ticks}  (${ticks / TICKS_PER_USD:.6f})")
        if ticks > args.max_usd * TICKS_PER_USD:
            print("  WARNING: this single call exceeded the cap you authorized.")

    if args.save is not None:
        target = args.save.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        print(f"\nRaw response written to {target}")
        print("This file may contain image bytes and a signed URL. Do not commit it.")

    print("\nNext: fill in the UNVERIFIED table in hackathon/COST_LEDGER.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
