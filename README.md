# Adjacency

[![CI](https://github.com/arunshar/adjacency/actions/workflows/ci.yml/badge.svg)](https://github.com/arunshar/adjacency/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](.python-version)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)
[![Live demo](https://img.shields.io/badge/Demo-Hugging%20Face-f59e0b?logo=huggingface&logoColor=white)](https://arun0808-adjacency-autopsy.hf.space)

**A brand-safety policy engine that compiles advertiser prose into something you can test.**

Adjacency is Spatial Atlas's typed-scene-graph, fail-closed, confidence-gated discipline pointed at ad adjacency. Advertiser prose becomes a typed, hashed, diffable `PolicySpec`. Frozen inventory is evaluated multimodally. Every proposed verdict passes deterministic gates before it can affect delivery. The resulting decision is compared with a keyword blocklist generated from the same prose.

The model proposes. Gates decide.

## Try the Autopsy

The [public Autopsy](https://arun0808-adjacency-autopsy.hf.space) is an offline replay. It has no xAI or Temporal credentials. Run it to inspect:

- `AGREE`: both systems produce the same delivery disposition.
- `OVER_BLOCK`: the keyword baseline withholds inventory that the compiled engine allows.
- `UNDER_BLOCK`: the keyword baseline allows inventory that the compiled engine withholds.
- `G1_SPAN_NOT_FOUND`: a proposed `ALLOW` becomes `REVIEW` when cited evidence does not reproduce the source span.
- The cited image region, full gate chain, audit payload, and human-review destination.

The dollar counter is an illustrative operator input. It is not a measured revenue claim. Its source is `artifacts/ui/economics_assumption.json`.

## Results

Every value below is copied from the file named beside it.

| Observed result | Artifact |
|---|---|
| 12/12 injected faults caught with 0/4 clean cases rejected | `artifacts/tuesday/synthetic_faults.json` |
| 68% grounding failure in raw-prompt run 1 | `evals/prompt_baseline/comparison.json` |
| 2% action disagreement across identical-input raw-prompt runs | `evals/prompt_baseline/comparison.json` |
| 44% of frozen decisions escalated to Tier 2 | `artifacts/wednesday/judge_report.json` |
| $6.12 per 1,000 decisions in measured blended judge cost | `artifacts/wednesday/judge_report.json` |
| Real Temporal Cloud transition from pending review through signal, adjudicated query state, and workflow completion | `artifacts/temporal/hitl_live_proof.json` |

These are failure-detection, grounding, stability, routing, cost, and protocol observations. They are not an accuracy claim. See [RESULTS.md](RESULTS.md) for the one-page evidence sheet.

## Architecture

The system has five connected parts, each anchored by source files:

1. Policy compilation: `src/adjacency/policy.py`, `src/adjacency/contracts.py`, and compile-time G0 in `src/adjacency/gates.py`.
2. Inventory and judging: `src/adjacency/inventory.py`, `src/adjacency/corpus.py`, `src/adjacency/tier_zero.py`, and `src/adjacency/judge.py`.
3. Deterministic admission: G1 through G6 in `src/adjacency/gates.py`.
4. Same-prose comparison and Autopsy: `src/adjacency/baseline.py`, `src/adjacency/delta.py`, `src/adjacency/autopsy.py`, and `src/adjacency/ui.py`.
5. Human review: the default in-process queue in `src/adjacency/hitl.py`, with the Temporal adapter isolated in `src/adjacency/temporal_hitl.py`.

Read [ARCHITECTURE.md](ARCHITECTURE.md) for the complete interaction map, file walkthrough, flows, and design decisions.

## Quick start

The Python version is pinned in `.python-version`. The deterministic core installs without model, media, UI, or Temporal dependencies.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest -q
```

Run the offline Autopsy with no API key:

```bash
.venv/bin/pip install -e ".[serve]"
.venv/bin/python app.py
```

External calls replay from content-addressed fixtures by default. Set `ADJ_RECORD=1` only when intentionally recording a live response. The default inventory source is `frozen_corpus`, as defined in `src/adjacency/sources.py`.

## Optional Temporal review backend

`ADJ_HITL_BACKEND` defaults to `in_process`. Temporal remains opt-in and owns only the human-review queue. The judge, gates, corpus, and public demo never depend on it.

```bash
.venv/bin/pip install -e ".[temporal]"
export ADJ_HITL_BACKEND=temporal
.venv/bin/python scripts/run_temporal_hitl_worker.py
```

The durable surface is deliberately small: one `AdjacencyHITLReview` workflow, one `adjudicate` signal, and one `queue_state` query in `src/adjacency/temporal_hitl.py`. The live proof in `artifacts/temporal/hitl_live_proof.json` is an integration transition, not a human label.

## Deliverables

- Paper source and compiled report: `paper/main.tex` and `paper/main.pdf`.
- Portable browser deck, PDF, and PowerPoint: `slides/adjacency_deck_portable.html`, `slides/adjacency_deck.pdf`, and `slides/adjacency_deck.pptx`.
- Recorded fallback run and capture metadata: `artifacts/demo/adjacency_fallback.mp4` and `artifacts/demo/adjacency_fallback.json`.
- Quality contract: [QUALITY.md](QUALITY.md).
- Judging evidence map: [judging-map.md](judging-map.md).

## License

Code is MIT licensed. Third-party evaluation text and media are not relicensed. See `corpus/README.md` for provenance handling.
