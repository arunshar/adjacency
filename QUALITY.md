# Quality Contract

Adjacency treats deterministic admission logic and network-facing code differently. The policy is asymmetric because the cost of a missed gate branch is much higher than the cost of an untested transport branch, while fixture replay can test transport behavior more faithfully than synthetic line coverage.

## Deterministic core

The following modules must retain complete line and branch coverage:

- `src/adjacency/contracts.py`
- `src/adjacency/gates.py`
- `src/adjacency/imagine_signal/canonical.py`
- `src/adjacency/imagine_signal/contracts.py`
- `src/adjacency/imagine_signal/mutations.py`
- `src/adjacency/imagine_signal/gates.py`
- `src/adjacency/imagine_signal/decisions.py`
- `src/adjacency/imagine_signal/receipts.py`

The enforced threshold and command live in `.github/workflows/ci.yml` under `Deterministic core must stay at 100 percent`.

The original contracts freeze typed inputs and outputs. The original gates recompute source spans, clause membership, monotonicity, severity coherence, budget state, and abstention behavior. ImagineSignal adds canonical content hashing, immutable workflow contracts, controlled mutation validation, IS0 through IS8 gates, evidence-capped actions, and digest-linked receipts. A failure returns a structured code and resolves toward a non-serving action.

## Package-wide floor

The remaining package has a 55% line and branch coverage floor configured in `pyproject.toml` and enforced by `.github/workflows/ci.yml`. This floor catches untested modules. It is not a claim that every module is exhaustively tested, and it is not the primary assurance mechanism for I/O.

I/O-heavy behavior uses recorded fixture replay and frozen artifacts:

- Content-addressed external-call replay: `src/adjacency/fixtures.py` and `fixtures/api/`.
- Inventory discovery and direct-status verification replay: `tests/test_inventory.py` and `tests/test_wednesday_fixture_replay.py`.
- Policy compilation and baseline replay: `tests/test_tuesday_fixture_replay.py`.
- Offline UI artifact validation: `tests/test_autopsy.py` and `tests/test_ui.py`.
- Temporal adapter unit and contract tests: `tests/test_temporal_hitl.py`.
- Synthetic Imagine request, response, and media replay: `fixtures/imagine_signal/api/`, `fixtures/imagine_signal/assets/`, `tests/imagine_signal/test_fixture_blobs.py`, and `tests/imagine_signal/test_imagine_client.py`.
- Frozen aggregate outcome replay: `fixtures/imagine_signal/outcomes/demo_family.json` and `tests/imagine_signal/test_outcomes.py`.
- Complete offline ImagineSignal receipt replay: `artifacts/imagine_signal/offline_demo.json` and `tests/imagine_signal/test_end_to_end_replay.py`.

The ImagineSignal fixtures and artifact are synthetic, deterministic evidence. They do not establish current provider behavior, production readiness, advertiser lift, or X Ads revenue.

The committed offline artifact contains three synthetic image assets, two aggregate signal estimates derived from four frozen outcome snapshots, an IS0 through IS8 decision receipt, and a final action of `TEST`. It also records `network_used: false`, `provider_call_used: false`, and `production_authorization: NOT_PRESENT`. These fields make the evidence boundary machine-checkable rather than dependent on prose.

## Latest local verification

On 2026-08-05 with Python 3.13.5, the non-e2e suite completed with 433 passing tests and 87.66% total line and branch coverage. The deterministic-core selection covered 1,153 statements and 432 branches at exactly 100%, with no missing lines or partial branches. This is a dated local measurement. The durable CI requirements remain the 100% deterministic-core gate and the 55% package-wide floor.

## CI checks

The workflow in `.github/workflows/ci.yml` performs:

- Dependency advisory scanning with a pinned `pip-audit` release.
- Ruff lint and formatting checks for `src`, `tests`, and `scripts`.
- Bandit scanning for the package source.
- Complete deterministic-core line and branch coverage.
- Credential-free verification of the frozen ImagineSignal fixtures and offline demo artifact.
- The package-wide suite and its configured coverage floor.
- A separate install that proves the core does not import model, media, UI, or Temporal packages.

Run the same checks locally:

```bash
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/bandit -q -c pyproject.toml -r src
.venv/bin/pytest -m "not e2e" -q \
  --cov=adjacency.contracts \
  --cov=adjacency.gates \
  --cov=adjacency.imagine_signal.canonical \
  --cov=adjacency.imagine_signal.contracts \
  --cov=adjacency.imagine_signal.mutations \
  --cov=adjacency.imagine_signal.gates \
  --cov=adjacency.imagine_signal.decisions \
  --cov=adjacency.imagine_signal.receipts \
  --cov-branch \
  --cov-report=term-missing --cov-fail-under=100
env -u XAI_API_KEY -u ADJ_RECORD \
  .venv/bin/python -I -B scripts/generate_imagine_signal_fixtures.py --verify-only
env -u XAI_API_KEY -u ADJ_RECORD \
  .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
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
