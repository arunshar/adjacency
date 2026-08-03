"""Compile advertiser prose into a grounded, cached :class:`PolicySpec`."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from adjacency.contracts import PolicySpec, normalize
from adjacency.gates import g0_source_spans
from adjacency.xai import ResponseClient, output_text

POLICY_COMPILER_SURFACE = "model.policy_compiler"


class PolicyCompileError(ValueError):
    """Raised when a model output cannot become an admitted policy."""


class PolicyCompiler:
    """One high-reasoning structured call, followed immediately by G0."""

    def __init__(self, client: ResponseClient, *, model: str = "grok-4.5") -> None:
        self.client = client
        self.model = model
        self._cache: dict[tuple[str, str, int], PolicySpec] = {}

    def compile(self, *, advertiser: str, prose: str, version: int = 1) -> PolicySpec:
        trusted_advertiser = advertiser.strip()
        trusted_prose = normalize(prose).strip()
        if not trusted_advertiser:
            raise PolicyCompileError("advertiser cannot be blank")
        if not trusted_prose:
            raise PolicyCompileError("advertiser prose cannot be blank")
        if version < 1:
            raise PolicyCompileError("policy version must be at least 1")

        cache_key = (trusted_advertiser, trusted_prose, version)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = self._payload(
            advertiser=trusted_advertiser,
            prose=trusted_prose,
            version=version,
        )
        response = self.client.create(surface=POLICY_COMPILER_SURFACE, payload=payload)
        try:
            decoded = json.loads(output_text(response))
            spec = PolicySpec.model_validate(decoded)
        except (json.JSONDecodeError, ValidationError) as error:
            raise PolicyCompileError("model returned an invalid PolicySpec") from error

        if spec.advertiser != trusted_advertiser:
            raise PolicyCompileError("model changed the trusted advertiser name")
        if spec.prose != trusted_prose:
            raise PolicyCompileError("model changed the trusted advertiser prose")
        if spec.version != version:
            raise PolicyCompileError("model changed the trusted policy version")
        if not spec.clauses:
            raise PolicyCompileError("model returned a policy with no clauses")

        failures = [result for result in g0_source_spans(spec) if not result.passed]
        if failures:
            codes = ", ".join(result.code or "G0_UNKNOWN" for result in failures)
            raise PolicyCompileError(f"G0 rejected the compiled policy: {codes}")

        self._cache[cache_key] = spec
        return spec

    def _payload(self, *, advertiser: str, prose: str, version: int) -> Mapping[str, Any]:
        prompt = (
            "Compile the advertiser's prose into a PolicySpec. Return one or more clauses. "
            "Every clause must quote an exact, contiguous source_text span from the prose, "
            "with zero-based Python character offsets and an exclusive source_end. Do not "
            "invent policy requirements. Keep the advertiser, prose, and version exactly as "
            "provided. Use severity 0 or 1 for ALLOW intent, 2 for REVIEW, and 3 or 4 for "
            "BLOCK intent. Clause ids must be unique and stable-looking.\n\n"
            f"Advertiser: {advertiser}\n"
            f"Version: {version}\n"
            f"Advertiser prose:\n{prose}"
        )
        return {
            "input": [{"content": prompt, "role": "user"}],
            "max_output_tokens": 8192,
            "model": self.model,
            "reasoning": {"effort": "high"},
            "store": False,
            "text": {
                "format": {
                    "name": "policy_spec",
                    "schema": PolicySpec.model_json_schema(),
                    "strict": True,
                    "type": "json_schema",
                }
            },
        }
