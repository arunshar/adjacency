# ImagineSignal decision cover

| Field | Current value |
|---|---|
| Document version | 0.2 |
| Status | Offline MVP implemented and verified; production no-go |
| Author | Arun Sharma |
| Date | 2026-08-05 |
| Product | ImagineSignal |
| Product definition | Controlled creative lineage, outcome learning, and evidence-gated next actions for Grok Imagine |
| Current launch mode | Local frozen replay only |
| Current evidence tier | `UNIT_TESTED`, `FROZEN_REPLAY`, and `SIMULATED` |
| Current decision | `GO` for offline MVP review; `NO_GO` for production data, writes, or auction influence |
| Current bounded action | `TEST`, meaning a proposal for a later authorized test only |
| Product DRI | Arun Sharma for prototype; production DRI TBD |
| Engineering DRI | TBD before internal shadow |
| Go or no-go decision maker | TBD before internal shadow |
| Target production date | Not set |
| Review cutoff | Before enabling live API recording, production-data reads, or any write path |
| Customer population | None |
| Traffic | 0 percent |
| Geography | Local development only |
| Can publish | No |
| Can spend | No |
| Can change ranking | No |
| Can change auction pricing | No |
| Rollback owner | Not needed for offline slice; TBD before shadow |
| Incident commander | TBD before live or restricted-data access |

## Decision

The first offline implementation slice is complete within the following boundaries:

1. Work is isolated under `src/adjacency/imagine_signal/`, `tests/imagine_signal/`, `fixtures/imagine_signal/`, and `artifacts/imagine_signal/`.
2. The implemented Imagine client is fixture-only. A missing fixture fails closed and cannot trigger a live call.
3. The slice contains no X Ads connector, no production data, and no production authorization.
4. Every recommendation is capped by evidence class.
5. Simulation can recommend `TEST`, but cannot emit a production promotion decision.
6. Existing Adjacency contracts and G0-G6 behavior remain separate.
7. No result is described as a measured image-quality, advertiser-lift, or revenue increase.

The deterministic demo replays three synthetic assets, joins four aggregate synthetic snapshots across two contexts, passes `IS0` through `IS8`, and produces final action `TEST`. See [the implementation status](12_IMPLEMENTATION_STATUS.md) for exact evidence and reproduction commands.

Automatic fallback if a boundary is unmet: stop at documentation or local deterministic tests and record the blocker in [the review checklist](10_REVIEW_CHECKLIST.md).

## Implemented and enabled offline

- Immutable campaign, mutation, asset, outcome, simulation, and receipt contracts.
- Deterministic creative-lineage and claim-admission gates.
- Synthetic campaign and outcome fixtures.
- A paper-linked, single-slot auction simulator with explicit scenario metadata.
- Paired baseline-versus-variant sensitivity runs.
- A replay-only Imagine client interface and fixture format.
- A command-line or local UI explanation of every decision.

All items in this section are local-only. Their evidence ceiling is `UNIT_TESTED`, `FROZEN_REPLAY`, or `SIMULATED` as labeled in the artifact.

## Explicitly disabled

- Live image generation. The replay path and secret checks are implemented, but no live provider adapter or authorized recording is part of this slice.
- X Ads reads or writes.
- Campaign publishing.
- Budget, bid, targeting, floor, reserve, or pacing changes.
- Ranking-signal export.
- User-level event ingestion.
- Cross-advertiser learning.
- Automated promotion.
- Public revenue claims.

## P0 blockers before read-only internal shadow

| Blocker | Required resolution | Owner |
|---|---|---|
| No named internal product and engineering owners | Name accountable owners and review cadence | TBD |
| No authorized live provider recording | Confirm API account, credits, model access, billing cap, credentials, and one bounded recording plan | Product and engineering, TBD |
| No approved data source | Define a read-only, aggregate, permitted-use outcome contract | Ads data owner, TBD |
| Unknown production auction details | Complete the auction-science model card against the actual scoped surface | Ads auction engineering, TBD |
| No approved evidence thresholds | Pre-register success, harm, sample, freshness, and override thresholds | Product and experimentation, TBD |
| No privacy or security review | Approve classification, retention, deletion, tenant isolation, and credentials | Privacy and security, TBD |
| No tested kill switch or rollback | Implement and drill the relevant disable paths | SRE, TBD |
| No causal evidence | Run authorized experiments in the sequence defined by the evaluation ladder | Experimentation, TBD |

## Five questions for an executive reviewer

1. Does controlled one-change-at-a-time creative generation solve a real advertiser workflow problem?
2. Is the first product goal generation efficiency and learning speed, rather than an unsupported revenue promise?
3. Which team owns the aggregate outcome feed and experimental authorization?
4. Which action is acceptable for the first internal beta: draft only, human-approved publish, or neither?
5. What evidence and countermetrics must be present before the product can mention revenue outside research notes?

## Re-review triggers

Re-open this decision when any of the following changes:

- A live xAI API key is introduced.
- A provider model alias or endpoint changes.
- Production or restricted data are requested.
- The product gains publishing, spending, or ranking permissions.
- The experiment unit, attribution window, auction mechanism, or primary metric changes.
- A public product, sales, press, or revenue claim is proposed.
