# ImagineSignal offline MVP implementation status

| Field | Value |
|---|---|
| Version | 0.2 |
| Status | Offline MVP implemented and verified; production no-go |
| Date | 2026-08-05 |
| Repository | `/Users/arunsharma/code/adjacency` |
| Launch mode | Local frozen synthetic replay only |
| Evidence classes | `UNIT_TESTED`, `FROZEN_REPLAY`, and `SIMULATED` |
| Production traffic | 0 percent |
| Current bounded action | `TEST`, which means propose a later authorized test only |

## Outcome

The bounded offline MVP is implemented. It can build a controlled family of synthetic ad images, prove which declared attribute changed, replay content-addressed image fixtures without credentials or network access, join aggregate synthetic outcome snapshots, run an explicitly simulated auction-sensitivity scenario, apply gates `IS0` through `IS8`, and write a deterministic decision receipt.

This completion statement applies only to the local offline slice. It does not mean the feature is production ready. No live xAI request was made, no X Ads data was read, no ad was published, no campaign money was spent, and no ranking or auction setting was changed.

The implementation is currently an uncommitted review worktree. No commit or push is implied by this status document.

## Completion matrix

| Capability | Implementation | Verification | Evidence boundary |
|---|---|---|---|
| Canonical identity and strict domain contracts | Complete in `src/adjacency/imagine_signal/canonical.py` and `contracts.py` | Deterministic tests cover stable hashes, validation, and immutable records | `UNIT_TESTED` |
| Controlled mutation and lineage | Complete in `mutations.py` | Tests cover one-axis mutation, locked attributes, and invalid lineage | `UNIT_TESTED` |
| Claim and action gates | Complete in `gates.py` and `decisions.py` | `IS0` through `IS8` pass for the frozen demo and fail closed in negative tests | `UNIT_TESTED` and `FROZEN_REPLAY` |
| Decision receipts | Complete in `receipts.py` | Append-once identity, prior-receipt linkage, and conflict behavior are tested | `UNIT_TESTED` |
| Imagine fixture adapter | Complete as replay-only code in `imagine_client.py`, `assets.py`, and `adapters/fixture_blobs.py` | Three synthetic PNG assets verify by request hash, response metadata, media hash, dimensions, and type | `FROZEN_REPLAY` |
| Aggregate outcomes | Complete in `outcomes.py` | Four synthetic aggregate snapshots join across two contexts; experiment, arm, duplicate, conflict, freshness, and zero-denominator behavior are tested | `FROZEN_REPLAY` |
| Auction sensitivity | Complete in `auction.py` | Seeded fixed-bid scenarios reproduce; adaptive bidder modes remain a research-only robustness extension | `SIMULATED` |
| End-to-end orchestration | Complete in `service.py` and `demo.py` | Credential-free replay produces the reviewed receipt and artifact | `FROZEN_REPLAY` plus `SIMULATED` |
| Production provider and X Ads connectors | Intentionally absent | No production write client exists in the demo path | `NO_GO` |

## Deterministic demo result

The reviewed artifact is `artifacts/imagine_signal/offline_demo.json`. Its embedded canonical payload SHA-256 is calculated over the artifact object before the `artifact_sha256` field is added:

```text
29997622e01e57b8f150a80e0c48dc2e91a131c5ccf99ebbbf7874660381c2df
```

The SHA-256 of the complete formatted JSON file bytes is:

```text
b17e9105f0de89772440c82938a69a7b25452784fc9c0667a4fe81a8f621ca73
```

The artifact records:

- Run mode `fixture`, with `network_used=false` and `provider_call_used=false`.
- No X Ads write client and no production authorization.
- Three verified synthetic assets: one control and two variants that change only `background_tone`.
- Four aggregate synthetic outcome snapshots across `home-feed` and `search`.
- Two frozen-replay `observed.ctr` estimates. The label names the metric namespace; the values are synthetic fixture totals, not X Ads observations.
- A seeded fixed-bid auction sensitivity result labeled `SIMULATED`.
- Passing results for gates `IS0` through `IS8`.
- Final action `TEST`. This action cannot publish, spend, change ranking, or establish a causal claim.
- A synthetic workflow comparison of 3 qualified outputs from 3 controlled generations versus 2 qualified outputs from 3 unstructured baseline generations. This is a fixture-backed pipeline check, not measured image quality, provider efficiency, advertiser lift, or revenue.

Any seller-revenue value inside the artifact is a scenario output from the local auction simulator. It is not observed X revenue, a forecast, or evidence that ImagineSignal changes revenue.

## Exact reproduction commands

Run these commands from the repository root. Unsetting both variables makes the replay-only boundary explicit.

```bash
cd /Users/arunsharma/code/adjacency
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/generate_imagine_signal_fixtures.py --verify-only
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
.venv/bin/pytest tests/imagine_signal -q
```

The two verification commands are read-only. A missing or conflicting fixture is terminal; verification does not fall back to a live provider call. Artifact regeneration is a separate explicit operation using `--write` and should occur only when the reviewed synthetic inputs or implementation intentionally change.

## Production blockers

The offline MVP must remain a production no-go until all applicable blockers have named owners, evidence, and sign-off:

1. Implement and review a production provider adapter behind the existing port, then authorize one bounded, cost-capped recording separately.
2. Confirm the correct xAI developer account, API credits, model access, rate limits, credential storage, and billing controls. A SuperGrok consumer subscription is not treated as API authorization or API credit.
3. Approve an aggregate X Ads outcome contract, permitted use, tenant isolation, retention, deletion, and privacy controls. Raw user events are outside the current scope.
4. Validate the auction model against the specific internal mechanism before using any sensitivity result for product decisions.
5. Add durable idempotent storage, access control, audit retention, observability, SLOs, alerting, a kill switch, rollback, and incident ownership.
6. Name product, engineering, ads data, experimentation, privacy, security, legal, and operations owners.
7. Pre-register authorized experiments with sample, freshness, harm, uncertainty, and stop thresholds.
8. Obtain causal evidence before making lift or revenue claims. Replay and simulation cannot supply that evidence.
9. Keep publishing, spending, targeting, bidding, pacing, ranking, floor, reserve, and auction write paths disabled until their own review and authorization.

## Review order

1. Read the [plain-language explanation](01_PLAIN_EXPLAINER.md) for the audience-level product story.
2. Read this status document for the exact completed boundary.
3. Inspect `artifacts/imagine_signal/offline_demo.json` and its evidence labels.
4. Run the three reproduction commands above.
5. Review the [decision cover](00_DECISION_COVER.md) and [evaluation and claims rules](07_EVALUATION_AND_CLAIMS.md).
6. Review `src/adjacency/imagine_signal/service.py`, then the contracts, gates, adapters, outcomes, auction, and tests.
7. Review the [system design](03_SYSTEM_DESIGN.md), [security and operations plan](08_SECURITY_PRIVACY_OPERATIONS.md), and [review checklist](10_REVIEW_CHECKLIST.md) before discussing any shadow or live phase.
8. For a fresh local Claude session, read the [current Claude handoff](13_CLAUDE_HANDOFF.md) and use the [paste-ready resume prompt](14_CLAUDE_RESUME_PROMPT.md).

## Next bounded phase

The next reasonable review target is a read-only internal shadow design using an approved aggregate data contract. A live Imagine recording is optional and separate. Neither step is authorized by this document.
