# ImagineSignal August 6 session handoff

> Historical handoff, completed on 2026-08-05. This file is retained for provenance and is superseded by [the offline MVP implementation status](12_IMPLEMENTATION_STATUS.md). Do not use the implementation-state statements below as current status.

| Field | Value |
|---|---|
| Handoff version | 0.1 |
| Prepared | 2026-08-05, America/Los_Angeles |
| Resume date | 2026-08-06 |
| Author | Arun Sharma |
| Repository | `/Users/arunsharma/code/adjacency` |
| Branch at preparation | `main` |
| HEAD at preparation | `cd218dd` |
| Python observed | 3.13.5 system and `.venv` |
| Current task | Begin PR 1 deterministic ImagineSignal contracts and canonical identity |
| Live API authorization | Not granted by this handoff |

## 1. Current state

The current repository implements Adjacency, an offline brand-safety decision and Autopsy system. ImagineSignal is not implemented in source code.

This session added a proposed production review packet under `docs/imagine_signal/` and one link in the root `README.md`. At handoff preparation, these changes are intentionally uncommitted:

```text
M README.md
?? docs/imagine_signal/
```

The expected documentation files are:

```text
docs/imagine_signal/README.md
docs/imagine_signal/00_DECISION_COVER.md
docs/imagine_signal/01_PLAIN_EXPLAINER.md
docs/imagine_signal/02_PRD.md
docs/imagine_signal/03_SYSTEM_DESIGN.md
docs/imagine_signal/04_TECHNICAL_SPEC.md
docs/imagine_signal/05_XAI_INTEGRATION.md
docs/imagine_signal/06_AUCTION_SCIENCE_MODEL_CARD.md
docs/imagine_signal/07_EVALUATION_AND_CLAIMS.md
docs/imagine_signal/08_SECURITY_PRIVACY_OPERATIONS.md
docs/imagine_signal/09_IMPLEMENTATION_PLAN.md
docs/imagine_signal/10_REVIEW_CHECKLIST.md
docs/imagine_signal/11_AUG6_SESSION_HANDOFF.md
docs/imagine_signal/adrs/0001-parallel-domain.md
docs/imagine_signal/adrs/0002-evidence-gated-promotion.md
docs/imagine_signal/adrs/0003-replay-first-imagine-adapter.md
```

Do not assume this snapshot is unchanged. Verify branch, HEAD, and worktree before editing.

## 2. Controlling decision

The current decision is:

- Conditional go for local deterministic implementation, frozen replay, and a read-only shadow design.
- No-go for production-data access, ad publishing, spend changes, bid or targeting changes, ranking-signal export, auction changes, or revenue claims.

The first session must not make a live xAI or X Ads call.

## 3. Read these files in order

1. `/Users/arunsharma/code/adjacency/AGENTS.md`, if present, plus the active task instructions.
2. `/Users/arunsharma/code/adjacency/docs/imagine_signal/00_DECISION_COVER.md`
3. `/Users/arunsharma/code/adjacency/docs/imagine_signal/01_PLAIN_EXPLAINER.md`
4. `/Users/arunsharma/code/adjacency/docs/imagine_signal/02_PRD.md`
5. `/Users/arunsharma/code/adjacency/docs/imagine_signal/adrs/0001-parallel-domain.md`
6. `/Users/arunsharma/code/adjacency/docs/imagine_signal/adrs/0002-evidence-gated-promotion.md`
7. `/Users/arunsharma/code/adjacency/docs/imagine_signal/adrs/0003-replay-first-imagine-adapter.md`
8. `/Users/arunsharma/code/adjacency/docs/imagine_signal/04_TECHNICAL_SPEC.md`
9. `/Users/arunsharma/code/adjacency/docs/imagine_signal/09_IMPLEMENTATION_PLAN.md`
10. `/Users/arunsharma/code/adjacency/QUALITY.md`
11. `/Users/arunsharma/code/adjacency/src/adjacency/contracts.py`
12. `/Users/arunsharma/code/adjacency/src/adjacency/gates.py`
13. `/Users/arunsharma/code/adjacency/src/adjacency/fixtures.py`
14. `/Users/arunsharma/code/adjacency/src/adjacency/xai.py`
15. `/Users/arunsharma/code/adjacency/tests/conftest.py`
16. `/Users/arunsharma/code/adjacency/.github/workflows/ci.yml`

Read the system design, xAI integration, auction model card, evaluation plan, operations plan, and review checklist before touching their corresponding later workstreams.

## 4. Preflight commands

Run exactly from the repository:

```bash
cd /Users/arunsharma/code/adjacency
git status --short
git branch --show-current
git rev-parse --short HEAD
git diff --check
git diff -- README.md docs/imagine_signal
.venv/bin/python --version
.venv/bin/pytest -m "not e2e" -q
```

Record the actual results in the next session's commentary or handoff. The preparation run passed on 2026-08-05, but the next session must re-establish the baseline because the worktree may change overnight.

Preparation verification:

```text
.venv/bin/pytest -m "not e2e" -q
143 passed in 3.69s

.venv/bin/ruff check src tests scripts
All checks passed

.venv/bin/ruff format --check src tests scripts
50 files already formatted

.venv/bin/bandit -q -c pyproject.toml -r src
Passed with no reported finding

git diff --check
Passed

Local Markdown link check
Passed
```

## 5. Worktree stop gate

Stop before editing when:

- Branch or HEAD differs and the difference is unexplained.
- There are changes in `src/adjacency/imagine_signal/` or `tests/imagine_signal/` that were not described here.
- Existing user changes overlap the planned files.
- The new documentation is missing, partially staged, or modified in a way that changes the product boundary.
- Baseline tests fail for a reason unrelated to the planned work.

If unrelated changes exist elsewhere, preserve them and continue only if the planned files do not overlap.

Do not reset, checkout, delete, or overwrite user changes.

## 6. Exact first implementation objective

Implement only the deterministic PR 1 skeleton:

```text
src/adjacency/imagine_signal/__init__.py
src/adjacency/imagine_signal/canonical.py
src/adjacency/imagine_signal/contracts.py
tests/imagine_signal/test_canonical.py
tests/imagine_signal/test_contracts.py
```

Do not add a provider client, fixture, image, API key, database, web route, X Ads adapter, UI, or auction simulator in this slice.

## 7. Exact implementation order

1. Create the package and test directories through `apply_patch`.
2. Write tests for canonical JSON and fixed SHA-256 vectors.
3. Write tests for frozen strict models and unknown-field rejection.
4. Implement `canonical.py` without importing private `adjacency.contracts._stable_hash`.
5. Implement the minimum core enumerations and contracts from the technical specification.
6. Add tests for duplicate IDs, invalid counts, invalid windows, invalid tenant and parent relations, Unicode normalization, and hash stability.
7. Run focused tests and coverage.
8. Run Ruff and formatting checks on the new paths.
9. Run the existing non-e2e suite.
10. Inspect `git diff` for changes outside the five planned files and documentation.
11. Update this handoff with actual test output, coverage, remaining decisions, and the next exact file.

Prefer the smallest contract set that proves the domain. Do not create speculative provider or production fields that cannot be validated. If the complete contract list is too large for one clean change, start with campaign, brand, mutation, asset, evidence class, next action, and receipt header, then document the deferral.

## 8. Focused verification

After the files exist:

```bash
.venv/bin/ruff check src/adjacency/imagine_signal tests/imagine_signal
.venv/bin/ruff format --check src/adjacency/imagine_signal tests/imagine_signal
.venv/bin/pytest tests/imagine_signal/test_canonical.py \
  tests/imagine_signal/test_contracts.py -q
.venv/bin/pytest tests/imagine_signal/test_canonical.py \
  tests/imagine_signal/test_contracts.py \
  --cov=adjacency.imagine_signal.canonical \
  --cov=adjacency.imagine_signal.contracts \
  --cov-branch --cov-report=term-missing --cov-fail-under=100
.venv/bin/pytest -m "not e2e" -q
git diff --check
```

If `--cov-branch` is unsupported by the installed version, inspect `pytest --help`, use the configured branch-coverage mechanism, and record the exact validated command before changing CI.

## 9. Live API and SuperGrok gate

SuperGrok can be used manually to explore prompts and compare images. It does not authorize code to make API calls.

Before any later live Imagine call, Arun must verify in the browser:

1. What the SuperGrok Usage page shows for `API`.
2. The selected xAI Console team.
3. API credit balance and postpaid limit.
4. Enabled image models.
5. The approved maximum call count and dollar cost.

The API key must never be pasted into Codex, a document, an issue, a fixture, a command stored in shell history, or source code. A later recording session should use a managed or silently entered environment secret.

If access or credit is missing, continue in fixture mode. PR 1 through PR 4 do not require the subscription or an API key.

## 10. Technical stop conditions

Stop and report rather than weakening a gate when:

- The only implementation path changes existing Adjacency `Action`, `Verdict`, `InventoryItem`, or G0-G6 semantics.
- A contract needs raw user-level behavior for the offline MVP.
- A fixture design would store raw base64, signed URLs, credentials, or confidential media in JSON.
- Missing or invalid cost would be represented as zero.
- A test requires live network access.
- Simulation is needed to emit a publish, spend, ranking, or revenue result.
- The supplied paper's unavailable repository is required for correctness.
- A requested Ads integration needs unapproved credentials or advertiser access.
- Existing baseline tests fail and the cause is not understood.

## 11. Known repository reuse constraints

- Reuse the frozen-model behavior, not the safety-domain types.
- Extract canonical hashing behavior into a public neutral helper; do not import the private function.
- Existing FixtureStore scans requests but not recorded responses. New Imagine recording must scan both.
- Existing JSON fixtures do not store large media bodies. Add a separate digest-linked blob fixture later.
- Existing cost parsing can collapse missing cost to zero. New contracts need explicit cost status.
- Existing budget G5 is not automatically in the current verdict chain. New orchestration must call budget admission around each paid operation.
- Existing in-process HITL is not durable production storage.
- Existing near-duplicate primitives are coarse filters, not proof that two images are semantically equivalent.

## 12. Open decisions that do not block PR 1

- First demo persona and mutation axis.
- Standard versus quality model routing policy.
- Exact response metric and outcome estimator.
- Auction paper reproduction tolerance.
- Asset storage choice after fixtures.
- Product naming and trademark review.
- Internal X Ads or aggregate-outcome access.
- Shadow and production owners, SLOs, retention, and experiment thresholds.

Do not invent these values inside contracts. Use versioned configuration or defer the field until its semantics are approved.

## 13. Ready-to-paste prompt for the new session

```text
Resume ImagineSignal in /Users/arunsharma/code/adjacency on August 6, 2026. First read docs/imagine_signal/11_AUG6_SESSION_HANDOFF.md completely, then follow its file order and stop gates. Verify branch, HEAD, worktree, and the existing non-e2e test baseline before editing. Preserve all user changes. The current authorized task is only PR 1: implement the deterministic ImagineSignal package initializer, canonical hashing module, core immutable contracts, and focused tests under src/adjacency/imagine_signal and tests/imagine_signal. Keep existing Adjacency Action, Verdict, InventoryItem, G0-G6, artifacts, and demo behavior unchanged. Do not make live xAI or X Ads calls, do not set ADJ_RECORD=1, do not add credentials, and do not commit or push. Hold the new canonical and contract core to complete line and branch coverage, run the focused and full non-e2e checks, inspect the diff, then update the handoff with exact verified results and the next action.
```

## 14. Completion record for the next session

Fill this in with evidence, not intentions:

```text
Date and time:
Branch:
HEAD before work:
Worktree before work:
Baseline test command and result:
Files changed:
Focused test command and result:
Coverage command and result:
Full test command and result:
Lint and format result:
git diff --check result:
Live network calls made: none expected
Credentials used: none expected
Blockers:
Open decisions changed:
Exact next file and task:
```
