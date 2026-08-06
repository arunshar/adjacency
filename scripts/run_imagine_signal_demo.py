#!/usr/bin/env python3
"""Build or verify the deterministic, credential-free ImagineSignal demo artifact."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from adjacency.imagine_signal.canonical import content_sha256
from adjacency.imagine_signal.demo import build_demo_request
from adjacency.imagine_signal.imagine_client import build_imagine_client
from adjacency.imagine_signal.service import OfflineImagineSignalService

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPO_ROOT / "artifacts" / "imagine_signal" / "offline_demo.json"


class DemoArtifactError(RuntimeError):
    """The generated artifact and committed evidence do not match."""


def build_artifact() -> dict[str, object]:
    """Run the complete offline service and add a self-verifying artifact digest."""

    client = build_imagine_client(fixture_root=REPO_ROOT / "fixtures" / "imagine_signal")
    result = OfflineImagineSignalService(client).run(build_demo_request(REPO_ROOT))
    artifact = result.to_dict()
    artifact.update(
        {
            "run_mode": "fixture",
            "network_used": False,
            "provider_call_used": False,
            "x_ads_write_client_present": False,
            "production_authorization": "NOT_PRESENT",
        }
    )
    artifact["artifact_sha256"] = content_sha256(artifact)
    return artifact


def encoded_artifact() -> str:
    return json.dumps(build_artifact(), ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def write_artifact(path: Path = ARTIFACT_PATH) -> None:
    """Atomically replace only the explicit demo artifact path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=path.parent,
            encoding="utf-8",
            prefix=f".{path.stem}.",
            suffix=".tmp",
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(encoded_artifact())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def verify_artifact(path: Path = ARTIFACT_PATH) -> None:
    """Require the committed artifact bytes to equal a fresh offline replay."""

    try:
        committed = path.read_text(encoding="utf-8")
    except OSError as error:
        raise DemoArtifactError(f"cannot read committed artifact {path}: {error}") from error
    expected = encoded_artifact()
    if committed != expected:
        raise DemoArtifactError(f"committed artifact differs from a fresh offline replay: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="verify the committed artifact, the default",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="explicitly regenerate the committed artifact, then verify it",
    )
    mode.add_argument(
        "--print",
        action="store_true",
        dest="print_artifact",
        help="print a fresh artifact without writing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_artifact:
        print(encoded_artifact(), end="")
        return 0
    if args.write:
        write_artifact()
    verify_artifact()
    print(
        json.dumps(
            {
                "artifact": str(ARTIFACT_PATH),
                "mode": "write-and-verify" if args.write else "verify-only",
                "network_used": False,
                "provider_call_used": False,
                "status": "verified",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
