# Quality Contract

Adjacency treats deterministic admission logic and network-facing code differently. The policy is asymmetric because the cost of a missed gate branch is much higher than the cost of an untested transport branch, while fixture replay can test transport behavior more faithfully than synthetic line coverage.

## Deterministic core

`src/adjacency/contracts.py` and `src/adjacency/gates.py` must retain complete line and branch coverage. The enforced threshold and command live in `.github/workflows/ci.yml` under `Deterministic core must stay at 100 percent`.

The contracts freeze typed inputs and outputs. The gates recompute source spans, clause membership, monotonicity, severity coherence, budget state, and abstention behavior. A failure returns a structured code and resolves toward a non-serving disposition.

## Package-wide floor

The remaining package has a 55% coverage floor configured in `pyproject.toml` and enforced by `.github/workflows/ci.yml`. This floor catches untested modules. It is not the primary assurance mechanism for I/O.

I/O-heavy behavior uses recorded fixture replay and frozen artifacts:

- Content-addressed external-call replay: `src/adjacency/fixtures.py` and `fixtures/api/`.
- Inventory discovery and direct-status verification replay: `tests/test_inventory.py` and `tests/test_wednesday_fixture_replay.py`.
- Policy compilation and baseline replay: `tests/test_tuesday_fixture_replay.py`.
- Offline UI artifact validation: `tests/test_autopsy.py` and `tests/test_ui.py`.
- Temporal adapter unit and contract tests: `tests/test_temporal_hitl.py`.

## CI checks

The workflow in `.github/workflows/ci.yml` performs:

- Dependency advisory scanning with a pinned `pip-audit` release.
- Ruff lint and formatting checks for `src`, `tests`, and `scripts`.
- Bandit scanning for the package source.
- Complete deterministic-core line and branch coverage.
- The package-wide suite and its configured coverage floor.
- A separate install that proves the core does not import model, media, UI, or Temporal packages.

Run the same checks locally:

```bash
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/bandit -q -c pyproject.toml -r src
.venv/bin/pytest -m "not e2e" -q \
  --cov=adjacency.contracts --cov=adjacency.gates \
  --cov-report=term-missing --cov-fail-under=100
.venv/bin/pytest -m "not e2e" \
  --cov --cov-report=term-missing --cov-fail-under=55
```

## Evaluation provenance

Evaluation sources are closed over the enum in `src/adjacency/sources.py`. Only `frozen_corpus` and `synthetic_faults` are valid evaluation sources. Every reported metric must name the committed JSON artifact that contains its numerator, denominator, or measured call record. The compact list is in `RESULTS.md`.

No result is copied from a console transcript. Live responses are first recorded, secret-scanned by `src/adjacency/fixtures.py`, then replayed into a stable artifact.

## Demo isolation

The default UI mode in `src/adjacency/ui.py` accepts only `demo`. It reads committed files through `src/adjacency/autopsy.py`. The deployment allowlist in `deploy/huggingface/stage.sh` contains no credentials, live fixtures, or Temporal configuration.

`ADJ_HITL_BACKEND` defaults to `in_process` in `src/adjacency/hitl.py`. Importing the public app does not import the Temporal SDK. The opt-in adapter lives in `src/adjacency/temporal_hitl.py`.

## Release freeze checklist

- Rebuild the paper and confirm no LaTeX warnings.
- Rebuild the browser deck, portable deck, PDF, and PowerPoint.
- Validate the fallback video container and its SHA-256 metadata.
- Exercise the public Space through its external route and a phone-sized viewport.
- Run the public-scope phrase gate from the private handoff.
- Run the full local CI command set.
- Push with ordinary Git history and wait for GitHub Actions to pass.
- Record any physical-device verification that could not be performed by the build machine as an explicit user-owned check.
