# ImagineSignal implementation plan

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Ready to begin deterministic implementation |
| Author | Arun Sharma |
| Plan date | 2026-08-05 |
| First implementation session | 2026-08-06 |
| Current repository baseline | `main` at `cd218dd` when inspected; verify again before work |

## 1. Working rules

1. Keep each change independently reviewable and green.
2. Preserve existing Adjacency public contracts, G0-G6 codes, artifacts, and demo behavior.
3. Implement contracts and gates before provider code.
4. Replay is default. A missing fixture is an error, never permission to call live.
5. Do not add X Ads writes, user-level data, or production credentials in the MVP.
6. Every reported number must point to a committed artifact.
7. Every evidence class has an action and claim ceiling.
8. Unknown cost, missing evidence, stale data, and ambiguous provider completion fail toward `HOLD`, `REVIEW`, or `STOP`.
9. Use `apply_patch` for hand edits and preserve unrelated user changes.
10. Do not commit or push unless the user explicitly requests it.

## 2. Target structure

The first slices stay inside one bounded package:

```text
src/adjacency/imagine_signal/
  __init__.py
  contracts.py
  canonical.py
  mutations.py
  gates.py
  decisions.py
  receipts.py
  ports.py
  assets.py
  outcomes.py
  auction.py
  imagine_client.py
  service.py

tests/imagine_signal/
  ...matching test modules...
```

Provider and storage adapters can move into `src/adjacency/imagine_signal/adapters/` when the ports are stable. A production HTTP service is a later workstream and should not be mixed into the deterministic-core pull request.

## 3. Pull-request sequence

### PR 0: specification packet

Scope:

- Add this review packet.
- Link it from the root README.
- Confirm current API and research sources.
- Record the current conditional-go boundary.

Acceptance:

- Markdown has no broken local links.
- Mermaid blocks parse in the review renderer or are visually checked.
- No unsupported current-state or revenue claim.
- No secret or account-specific credential.
- `git diff --check` passes.

### PR 1: canonical identity and contracts

Files:

```text
src/adjacency/imagine_signal/__init__.py
src/adjacency/imagine_signal/canonical.py
src/adjacency/imagine_signal/contracts.py
tests/imagine_signal/test_canonical.py
tests/imagine_signal/test_contracts.py
```

Tasks:

1. Implement public canonical JSON and stable SHA-256 without importing the private `_stable_hash` helper.
2. Add frozen, strict contracts for `CampaignSpec`, `BrandSpec`, `MutationSpec`, `CreativeAsset`, `OutcomeSnapshot`, `SignalEstimate`, `AuctionScenario`, `AuctionSensitivityResult`, and `DecisionReceipt`.
3. Add the initial enumerations and evidence classes.
4. Define which timestamps and transport metadata are excluded from semantic hashes.
5. Add fixed hash vectors and Unicode normalization tests.
6. Test unknown fields, duplicate identifiers, invalid windows, invalid counts, and invalid parent relationships.

Acceptance:

- No network, provider SDK, database, UI, or Temporal import.
- Complete line and branch coverage for the new contract and canonical modules.
- Existing tests remain green.
- Contract schema and hash vectors are reviewable.

### PR 2: controlled mutations, gates, and decisions

Files:

```text
src/adjacency/imagine_signal/mutations.py
src/adjacency/imagine_signal/gates.py
src/adjacency/imagine_signal/decisions.py
src/adjacency/imagine_signal/receipts.py
tests/imagine_signal/test_mutations.py
tests/imagine_signal/test_gates.py
tests/imagine_signal/test_decisions.py
tests/imagine_signal/test_receipts.py
```

Tasks:

1. Validate one family axis and immutable locked attributes.
2. Implement `IS0` through `IS8` as pure functions.
3. Implement the evidence-to-action ceiling.
4. Retain both proposed and final action in every receipt.
5. Add human-approval fields without adding a write action.
6. Add Hypothesis tests for malformed lineages, budgets, windows, and evidence/action pairs.

Acceptance:

- Every failure branch has a stable code.
- Rationale cannot affect a decision.
- `SIMULATED` evidence cannot exceed `TEST`.
- Complete line and branch coverage for contracts and gates.

### PR 3: fixed-bid auction-sensitivity kernel

Files:

```text
src/adjacency/imagine_signal/auction.py
tests/imagine_signal/test_auction.py
evals/imagine_signal/paper_scenarios/
scripts/run_imagine_signal_auction_eval.py
```

Tasks:

1. Implement explicit single-slot first-price, second-price, and soft-floor arithmetic.
2. Add fixed-bid query-conditioned scoring and paired baseline/variant runs.
3. Record score distance, boundary crossings, allocations, simulated seller revenue, and simulated advertiser utility.
4. Add common-randomness IDs and scenario hashes.
5. Add hand-calculated cases.
6. Add a paper-linked multi-query scenario without hard-coding the answer.
7. Write artifact output with evidence label `SIMULATED`.

Acceptance:

- Zero signal produces zero paired score difference.
- Pricing branches pass hand calculations.
- Repeated seeded runs reproduce.
- No code path calls X Ads or exports a ranking signal.
- Report states scenario assumptions and limitations.

### PR 4: binary fixture and replay-only Imagine adapter

Files:

```text
src/adjacency/imagine_signal/ports.py
src/adjacency/imagine_signal/assets.py
src/adjacency/imagine_signal/imagine_client.py
src/adjacency/imagine_signal/adapters/fixture_blobs.py
tests/imagine_signal/test_assets.py
tests/imagine_signal/test_imagine_client.py
tests/imagine_signal/test_fixture_replay.py
```

Tasks:

1. Define provider-independent generate and edit requests.
2. Implement a replay-only client with no live transport.
3. Store sanitized JSON metadata separately from content-addressed media bytes.
4. Scan both request and response metadata for secrets.
5. Verify media digest, length, type, and dimensions.
6. Ensure missing fixtures cannot instantiate or call a live transport.
7. Add exact and coarse near-duplicate checks using existing primitives where appropriate.

Acceptance:

- Full family replay works with network blocked and no key.
- Corrupt bytes, wrong dimensions, secret responses, and signed URLs fail.
- Unknown provider cost remains unknown and blocks paid escalation.
- Existing JSON fixture behavior remains compatible.

### PR 5: one bounded live Imagine recording

This slice is optional for the hackathon and requires explicit account and cost approval.

Tasks:

1. Verify team credits, enabled models, postpaid setting, and rate limit in `console.x.ai`.
2. Add direct JSON HTTP or the first-party xAI SDK behind the existing port.
3. Use a dated model alias and one non-sensitive 1K standard request.
4. Record resolved model, moderation status, request ID, latency, actual cost ticks, and verified media bytes.
5. Remove the credential and prove offline replay.

Acceptance:

- The approved dollar cap is not exceeded.
- No credential, authorization header, base64 body, or signed URL enters the fixture or log.
- The recorded response replays without network.
- The live and replay normalized result shapes match.

### PR 6: outcome snapshots and signal estimation

Files:

```text
src/adjacency/imagine_signal/outcomes.py
tests/imagine_signal/test_outcomes.py
fixtures/imagine_signal/outcomes/
```

Tasks:

1. Ingest aggregate synthetic or frozen snapshots only.
2. Deduplicate by tenant, source, and snapshot ID plus digest.
3. Validate campaign, creative, context, arm, source, window, and freshness.
4. Compute a declared response estimate and interval.
5. Keep observed, predicted, and simulated metric namespaces separate.
6. Add delayed, missing, duplicate, out-of-order, and cross-arm tests.

Acceptance:

- No raw user event contract in the prototype optimizer.
- Missing or stale evidence produces `HOLD`.
- Derived metrics are recomputable from the snapshot.
- Zero denominators produce unavailable metrics, not zero.

### PR 7: end-to-end offline service and Creative Autopsy

Files:

```text
src/adjacency/imagine_signal/service.py
tests/imagine_signal/test_service.py
tests/imagine_signal/test_end_to_end_replay.py
artifacts/imagine_signal/
```

Tasks:

1. Orchestrate brief, family, replay, asset checks, outcomes, sensitivity, gates, and receipt.
2. Enforce idempotency and expected versions.
3. Produce one exportable receipt and a simple local explanation.
4. Build a frozen demo family with one axis, two contexts, one control, and up to four variants.
5. Compare generation allocation with an equal-budget baseline.

Acceptance:

- Credential-free end-to-end replay.
- Every displayed number references an artifact.
- No production write client exists.
- The result page distinguishes replay, simulation, and proposed next test.

### PR 8: adaptive bidder research extension

Tasks:

1. Implement Hedge and EXP3-IX independently from the paper description.
2. Add predeclared horizons, seeds, burn-in, and convergence diagnostics.
3. Reproduce paper sanity scenarios within a documented tolerance.
4. Report both learners together.
5. Trigger `IS7_ASSUMPTION_SIGN_CONFLICT` when conclusions reverse.

Acceptance:

- Non-converged runs are invalid, not silently averaged.
- Unfavorable results remain in the artifact.
- No soft-floor optimization or production inference.

### PR 9 and later: shadow, persistence, approval, and service infrastructure

Only after the offline prototype is accepted:

- Durable metadata and object storage.
- Outbox or durable job execution.
- Authenticated tenant-scoped API.
- Read-only aggregate outcome adapter.
- Creative-specific durable review.
- Observability, cost, and deletion workflows.
- X Ads read-only analytics and draft-only adapter.

Each capability gets its own review and tests. Do not combine persistence, auth, X Ads, publishing, and experiment integration into one change.

## 4. First August 6 implementation session

### Objective

Complete PR 1's deterministic skeleton and leave the repository green. Do not make a live API call.

### Step-by-step

1. Read the files in [the session handoff](11_AUG6_SESSION_HANDOFF.md) in order.
2. Record branch, commit, worktree, Python, and current test status.
3. Resolve any overlapping user changes before editing.
4. Create only the package initializer, `canonical.py`, `contracts.py`, and their two test files.
5. Start with tests for strict frozen models and known hash vectors.
6. Implement the smallest code that passes those tests.
7. Add malformed and property-based cases.
8. Run focused lint, format check, test, and coverage.
9. Run the existing non-e2e suite.
10. Inspect the diff for accidental current-domain changes.
11. Update the handoff with actual verified results and the next exact task.

### Expected artifacts

- New deterministic package skeleton.
- Contract diagram or schema output only if useful for review.
- Focused test and coverage output.
- No fixtures, generated images, credentials, paid calls, or X Ads code.

## 5. Local commands

Initial discovery:

```bash
cd /Users/arunsharma/code/adjacency
git status --short
git branch --show-current
git rev-parse --short HEAD
python3.13 --version
```

Environment, if the existing `.venv` is absent:

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[test]"
```

Focused checks after PR 1 files exist:

```bash
.venv/bin/ruff check src/adjacency/imagine_signal tests/imagine_signal
.venv/bin/ruff format --check src/adjacency/imagine_signal tests/imagine_signal
.venv/bin/pytest tests/imagine_signal/test_canonical.py \
  tests/imagine_signal/test_contracts.py -q
```

Coverage command to validate before adding to CI:

```bash
.venv/bin/pytest tests/imagine_signal/test_canonical.py \
  tests/imagine_signal/test_contracts.py \
  --cov=adjacency.imagine_signal.canonical \
  --cov=adjacency.imagine_signal.contracts \
  --cov-branch --cov-report=term-missing --cov-fail-under=100
```

Full existing checks:

```bash
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/bandit -q -c pyproject.toml -r src
.venv/bin/pytest -m "not e2e" -q
git diff --check
```

Do not set `ADJ_RECORD=1` during PR 1 through PR 4.

## 6. Engineering acceptance matrix

| Capability | Unit | Fixture integration | Statistical or evaluation | Security | Live proof |
|---|---|---|---|---|---|
| Contracts and hashes | Required | Not applicable | Hash-vector artifact | Strict fields and tenant IDs | Not needed |
| Mutation and gates | Required, 100 percent core | Frozen family | Synthetic fault suite | Evidence ceiling | Not needed |
| Auction fixed-bid | Hand arithmetic | Frozen scenarios | Paired simulation | No write path | Not needed |
| Imagine adapter | Request mapping | Required, network blocked | Cost and duplicate metrics | Request and response scan | One bounded call later |
| Outcomes | Window and join logic | Frozen snapshots | Missingness and uncertainty | Source auth later | Shadow later |
| Service | Idempotency and modes | End-to-end replay | Same-budget comparison | Tenant tests | Shadow later |
| Draft or ranking integration | Authorization | Sandbox or staging | Authorized experiment | Full review | Required before use |

## 7. Parallel work that can begin after PR 1

- Product reviewer resolves the first demo user, axis, and primary efficiency metric.
- Imagine reviewer validates exact request and response examples for the selected model alias.
- Ads-science reviewer specifies the fixed-bid demo scenario and paper-reproduction tolerance.
- Experimentation reviewer drafts the later display-only estimand and assignment unit.
- Security and privacy reviewers classify assets, prompts, outcomes, and receipts.
- Design reviewer sketches the family, evidence, sensitivity, and receipt screens.

None of these workstreams authorizes a live call or production data.

## 8. Definition of MVP done

The offline MVP is done when:

- A reviewer can submit or load one frozen campaign brief.
- The system produces one control and a small one-axis family through replay.
- Every asset has verified lineage, media hash, provider metadata, and cost status.
- Aggregate frozen outcomes join exactly or fail visibly.
- Signal and auction sensitivity are shown separately.
- Every recommendation passes IS0 through IS8.
- The receipt states what changed, what was measured, what was simulated, what it cost, and why the next action is allowed.
- The entire demo runs without credentials or network.
- Existing Adjacency tests and public demo behavior remain unchanged.
- No screen or document claims measured revenue lift.

## 9. Definition of production done

Production is a separate milestone. It requires approved owners, internal system contracts, tenant isolation, durable storage and execution, aggregate data access, SLOs, on-call, security and privacy reviews, export and deletion, experiment authorization, causal evidence, countermetric health, tested kill switches and rollback, support readiness, and a fresh go or no-go review.

