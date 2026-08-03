# Adjacency

**A brand-safety policy engine that compiles advertiser prose into something you can test.**

An advertiser writes their policy in three sentences of English. Adjacency compiles it into
a typed, hashed, diffable `PolicySpec`, evaluates inventory against it multimodally, passes
every verdict through seven deterministic fail-closed gates, and reports the delta against
what a keyword blocklist would have done, split into two directions that matter differently:

- **Under-blocks**: risk the blocklist could not see, because it was in the image.
- **Over-blocks**: safe inventory the blocklist demonetized.

The second one is the half that costs money and that nobody demos.

## The design claim

A language model does exactly three things here: compile prose into a `PolicySpec` (once,
cached), judge adjacency on the residual that survives deterministic triage, and write a
human-readable rationale. Everything else is a pure function.

**The rationale is display-only.** Every decision is computed from structured fields
(`action`, `severity`, `clause_ids`, `evidence`) that a gate checks mechanically. Prose is
never load-bearing. A model that writes a persuasive paragraph cannot argue its way past a
lookup table.

## The gates

| Gate | Checks | When |
|---|---|---|
| G0 | Every clause's span reproduces its quoted prose exactly | compile time |
| G1 | Every cited text span is present verbatim, and every box lies inside its frame | per verdict |
| G2 | Every cited clause exists at that policy version | per verdict |
| G3 | A revision cannot flip a holdout item BLOCK to ALLOW without logged approval | per revision |
| G4 | `action` equals `SEVERITY_ACTION[severity]` | per verdict |
| G5 | Token, tool-call, and wallclock caps | per run |
| G6 | Below the confidence floor, or when two effort levels disagree, never ALLOW | per verdict |

G1 is the hallucination gate. G3 is the reward-hacking gate: absent it, the cheapest way to
make any brand-safety metric look good is to loosen the policy until everything is
deliverable, and the loosening is invisible because it shows up as more inventory rather
than as an incident.

Fail-closed means every failure resolves toward not serving an ad. `REVIEW` is a fail-closed
outcome, not a neutral one.

## Status

The deterministic core, fixture recorder, fixed inventory-source switch, delta engine,
near-duplicate clustering, policy compilation, same-prose keyword baseline, and seeded synthetic
faults are implemented and tested. `InventoryFetcher` discovers candidates through recorded
`x_search` calls, then verifies direct X status sources before the corpus can be frozen.
`AdjacencyJudge` routes each item through deterministic Tier 0, low-reasoning Tier 1, and
high-reasoning Tier 2 under explicit escalation predicates. The UI is next.

The recorded demo compiled four grounded clauses in `artifacts/tuesday/policy_spec.json`.
The baseline contains 73 normalized terms in `artifacts/tuesday/baseline_blocklist.json`.
The seeded evaluation caught all 12 injected faults and rejected none of its four clean
cases. The full cases and gate codes are in `artifacts/tuesday/synthetic_faults.json`.

The frozen Wednesday corpus contains 50 verified items and 18 locally stored media items. Its
content hash and every media SHA-256 digest are in `corpus/frozen/manifest.json`. The live judge
routed 52 percent of items to Tier 0, 4 percent to Tier 1, and 44 percent to Tier 2. Its measured
blended cost was $6.117936 per 1,000 decisions. Routing, latency, cost, gate-failure counts, and the
corpus hash are in `artifacts/wednesday/judge_report.json`. These are routing and cost measurements,
not an accuracy claim.

The raw-prompt comparison used the same policy prose and the same frozen 50-item corpus twice. The
runs disagreed on one action. Their strict evidence checks failed 34 of 50 claims in the first run
and 46 of 50 in the second because the returned offsets did not reproduce the quoted source text.
The complete verdicts, failures, measurements, policy prose hash, and corpus hash are in
`evals/prompt_baseline/`.

## Quick start

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest -q
```

The deterministic core has no model dependency. `pip install -e .` is enough to run every
gate test. `[model]` is only needed once you want to score real inventory.

External calls replay from content-addressed fixtures by default. Set `ADJ_RECORD=1` only
when intentionally recording live responses. `ADJ_FIXTURE_DIR` overrides the default
`fixtures/api` path.

Rebuild the Tuesday artifacts from the recorded responses without an API key:

```bash
PYTHONPATH=src .venv/bin/python scripts/build_tuesday_artifacts.py
```

Replay Wednesday discovery, source verification, judging, and both raw-prompt runs without an API
key. Replay verifies the committed corpus and evaluation outputs without replacing live latency
measurements:

```bash
PYTHONPATH=src .venv/bin/python scripts/freeze_wednesday_corpus.py
PYTHONPATH=src .venv/bin/python scripts/run_wednesday_evals.py
```

The blocklist is Arun's comparison baseline, not X's internal blocklist. It is generated
from the exact advertiser prose stored in the compiled `PolicySpec`, and its artifact keeps
the source policy hash and source prose beside the generated terms.

`ADJ_SOURCE` has four fixed values: `grok_x_search`, `live_x_api`, `frozen_corpus`, and
`synthetic_faults`. The default is `frozen_corpus`. Evaluation numbers may come only from
`frozen_corpus` or `synthetic_faults`.

## Layout

```
src/adjacency/
  baseline.py    same-prose keyword expansion and deterministic baseline matching
  corpus.py      verified local corpus freezing and content hashing
  contracts.py   the four frozen types: PolicySpec, InventoryItem, Verdict, DeltaRow
  delta.py       deterministic engine-versus-baseline comparison
  fixtures.py    content-addressed record and replay for external calls
  gates.py       the seven gates, all pure functions
  inventory.py   recorded x_search discovery plus direct-status verification
  judge.py       deterministic, low-effort, and high-effort escalation ladder
  model_metrics.py  per-call latency, token, and cost measurements
  near_dup.py    pHash and MinHash near-duplicate clustering
  policy.py      cached structured compilation with compile-time G0
  prompt_baseline.py  two raw free-text policy runs and strict comparison
  sources.py     the fixed ADJ_SOURCE switch
  synthetic_faults.py  seeded gate fault injection and measurement
  tier_zero.py   zero-cost clean-text decisions
  xai.py         recorded raw client for the xAI Responses API
artifacts/tuesday/
  policy_spec.json, baseline_blocklist.json, synthetic_faults.json
artifacts/wednesday/
  inventory_discovery.json, judge_report.json, judge_traces.json
corpus/
  frozen/manifest.json, media/*.jpg
evals/prompt_baseline/
  run_1.json, run_2.json, comparison.json
tests/
  test_*.py      focused branch and fixture-replay coverage
```

## Text offsets

Spans are character offsets into NFC-normalized text, not bytes and not UTF-16 code units.
This is load-bearing on a platform whose posts are full of emoji. The family emoji is 1
grapheme, 7 Python characters, 25 UTF-8 bytes, and 11 UTF-16 code units, and a model asked
for "the byte offset" will not reliably give you any of those. `Evidence.quote` is the
source of truth. The offsets are a claim about where it appears, and G1 checks that claim
rather than trusting the model's arithmetic.

## License

Code is MIT licensed. Third-party evaluation text and media are not relicensed. See
`corpus/README.md` for provenance handling.
