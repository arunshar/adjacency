# Product requirements document: ImagineSignal

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed for product, engineering, ads-science, and launch review |
| Author | Arun Sharma |
| Date | 2026-08-05 |
| Product owner | Arun Sharma for prototype; production owner TBD |
| Engineering owner | TBD |
| Approvers | Product, Imagine API, Ads engineering, experimentation, security, privacy, SRE, finance |
| Dependencies | Grok Imagine API, aggregate outcome source, existing Adjacency patterns, approved experiment service |
| Open blockers | Owners, thresholds, outcome access, internal mechanism details, privacy, security, rollback |

## 1. Overview

### Problem

Image-generation systems make it inexpensive to create many visually different ads, but they do not tell an advertiser which controlled change produced a useful outcome or whether another generation is economically justified. Unstructured variation creates three forms of waste:

1. Attribution waste: many attributes change, so the team cannot identify the useful change.
2. Generation waste: low-value variants receive the same generation budget as promising families.
3. decision waste: predicted engagement, measured engagement, simulated auction effects, and real revenue are mixed into one unsupported story.

### Solution

ImagineSignal is a creative-lineage and outcome-learning system that generates controlled Grok Imagine variants, measures what happens after generation, and recommends whether to keep, edit, test, hold, review, or stop an asset.

The core product is controlled creative mutation. Each experiment declares one mutable attribute and a set of locked attributes. Every output keeps an immutable parent-child lineage and cost record. A separate Auction Sensitivity Layer explores whether a measured signal could matter near a ranking boundary. Deterministic promotion gates cap each recommendation according to its evidence class.

### Product thesis

Purposeful generation should improve the amount of reusable evidence obtained per generation dollar. If later randomized experiments show that the resulting creative signal improves user response without harming advertisers or participation, the feature may also improve ads economics. That later outcome is a hypothesis, not a current result.

### Success measures

Targets must be approved before shadow or live evaluation. This PRD defines the metrics but does not fabricate baselines or thresholds.

| Metric | Definition | Phase first measured | Target |
|---|---|---|---|
| Controlled-family validity | Families where exactly one declared mutation axis changed and all locked constraints passed, divided by generated families | Offline | Proposed target: 100 percent for admitted families |
| Lineage completeness | Assets with valid tenant, campaign, parent, root, request hash, media hash, model, cost, and trace fields | Offline | Proposed target: 100 percent for admitted assets |
| Qualified creative yield | Creatives admitted for an approved test, divided by generated creatives | Offline then shadow | TBD after baseline |
| Cost per qualified creative | Reconciled Imagine API cost divided by admitted test creatives | Shadow | TBD after baseline |
| Duplicate generation rate | Paid outputs rejected as materially duplicate, divided by paid outputs | Replay then shadow | Baseline first; reduction target TBD |
| Time to testable family | Time from admitted brief to a complete family ready for human review | Shadow | TBD with user research |
| Outcome join completeness | Eligible aggregate outcomes joined to exact creative and experiment identifiers | Shadow | Launch threshold TBD; missing data always causes `HOLD` |
| Human override rate | Human decisions that reverse a recommendation, by reason code | Draft beta | Monitor and diagnose; threshold TBD |
| Repeat workflow use | Eligible advertisers or operators who start another controlled family | Draft beta | TBD |
| Causal response effect | Treatment effect on the pre-registered response metric | Authorized experiment | No claim before experiment |
| Causal billed-revenue effect | Treatment effect on billed revenue per eligible impression | End-to-end authorized experiment | No claim before experiment |

Countermetrics are advertiser ROAS, cost per acquisition, fill, small-advertiser participation, query coverage, advertiser concentration, negative feedback, hide or report rate, session continuation, creative fatigue, approval workload, support contacts, API cost, and incident rate.

## 2. Context and background

### Why now

- The Grok Imagine API provides production-facing image generation and editing surfaces, including multiple images, aspect-ratio and resolution controls, moderation metadata, and file reuse.
- Generating variants is becoming easier, which increases the value of controlling and learning from those variants.
- The existing Adjacency repository already demonstrates immutable typed contracts, stable hashes, deterministic fail-closed gates, fixture replay, and a human-review boundary.
- The supplied auction paper offers a useful simulation discipline for query-dependent CTR and bidder adaptation, while also showing why one favorable mechanism result cannot be generalized.

### Strategic alignment

| Area | Contribution |
|---|---|
| Grok Imagine engagement | Encourages iterative, evidence-driven generation rather than one-off novelty use |
| Imagine API revenue | Creates a justified next-generation loop while measuring and reducing waste |
| X Ads advertiser value | Connects controlled creative choices to measurable outcomes and reviewable next actions |
| X Ads economics | Produces testable hypotheses about when a small response signal may affect selection boundaries |
| Sales and enterprise adoption | Provides lineage, cost, reason codes, and exportable decision receipts |
| Platform efficiency | Uses duplicate checks, staged model quality, budget caps, and stop decisions |
| Safety and advertiser integrity | Preserves provider moderation and current ads-policy enforcement as mandatory guardrails |

### Research contribution and boundary

The supplied paper models a single-slot auction in which a bidder's score is bid times click-through rate and evaluates behavior under Hedge and EXP3-IX. It motivates a sensitivity question: if a creative changes click probability slightly, when could that alter an allocation or price outcome?

The paper does not test generated creatives, estimate a causal creative effect, or validate a production publisher-revenue lift. The Auction Sensitivity Layer therefore remains a labeled simulation until internal mechanism data and authorized experiments exist.

## 3. Users, stories, and acceptance criteria

### Advertiser creative strategist

As a creative strategist, I want to change one visual choice at a time so that a better result teaches me what to reuse.

Acceptance criteria:

- The brief declares exactly one mutation axis for the family.
- Locked attributes are visible before generation.
- Each child names its parent, mutation level, request hash, and output hash.
- A family with multiple undeclared changes is rejected or sent to review.
- The strategist can see cost and outcome evidence beside each variant.

### Campaign operator

As a campaign operator, I want a clear next action with no hidden side effects so that I remain in control of publishing and spend.

Acceptance criteria:

- The action is one of `KEEP`, `EDIT`, `TEST`, `HOLD`, `REVIEW`, or `STOP` in the MVP.
- No MVP action publishes, spends, changes targeting, or changes ranking.
- The receipt shows every passed and failed gate.
- A missing, stale, or mismatched outcome produces `HOLD`, never a winner.
- Retrying the same accepted request is idempotent.

### Ads optimization scientist

As an ads scientist, I want measured response separated from modeled auction sensitivity so that I can review assumptions and avoid false causal claims.

Acceptance criteria:

- Observed CTR, predicted CTR, and simulated CTR are separate fields and never silently substituted.
- Every simulation names its mechanism, bidder model, seed, horizon, and scenario hash.
- Baseline and variant use paired randomness.
- Hedge and EXP3-IX results appear together when either is reported.
- Sign disagreement produces `REVIEW` and blocks a robust economic conclusion.

### Imagine API partner developer

As a developer, I want a stable API and fixture mode so that I can integrate without paying for every local test or depending on provider uptime.

Acceptance criteria:

- Replay is the default and requires no credential.
- A live recording requires an explicit environment flag and a scoped API key.
- Provider requests have idempotency, time, concurrency, and dollar caps.
- Temporary provider URLs are consumed immediately or outputs are persisted by file ID.
- Every provider response records the resolved model and moderation disposition when exposed.

### Enterprise brand approver

As a brand approver, I want fixed brand constraints and human review so that experimentation does not silently alter protected content.

Acceptance criteria:

- The brief distinguishes mutable and locked attributes.
- Logos, product identity, claims, required disclosures, and prohibited elements can be locked.
- Provider moderation failure is terminal for that output and is not retried to bypass moderation.
- Existing ads-policy and legal approvals remain external requirements.
- Human overrides require an actor, reason, timestamp, and receipt update.

### Launch and incident operator

As an operator, I want independent kill switches and traceable failures so that I can contain cost, data, or write-path incidents.

Acceptance criteria:

- Generation, outcome ingestion, recommendation, ranking export, publishing, and tenant access have independent switches before their respective phases.
- Every request has a trace ID from brief through receipt.
- No credential, raw user event, or private prompt appears in general logs or fixtures.
- The system degrades to `HOLD`, `REVIEW`, `KEEP`, or `STOP`, never an unbounded generation loop.

## 4. Requirements

### P0 functional requirements

1. Define immutable, versioned contracts for campaign, brand constraints, mutation, asset, outcome, scenario, gate result, decision, and receipt.
2. Generate deterministic content hashes from canonical, secret-free payloads.
3. Validate that each admitted family has one mutation axis and a valid parent-child lineage.
4. Support a replay-only Imagine adapter with committed synthetic fixtures.
5. Support text-to-image and single-image edit request shapes behind one small client protocol.
6. Record model alias, resolved model when available, dimensions, moderation disposition, latency, and exact returned API cost when available.
7. Store output bytes by content digest; never depend on an expired temporary URL.
8. Detect exact duplicates before testing and provide a replaceable near-duplicate interface.
9. Ingest only aggregate synthetic or approved outcome snapshots in the MVP.
10. Estimate response with uncertainty and explicit sample and window metadata.
11. Run paired fixed-bid auction sensitivity; add Hedge and EXP3-IX as a research extension before making a robustness statement.
12. Execute deterministic `IS0` through `IS8` gates and emit stable codes.
13. Enforce an evidence-to-action ceiling. `SIMULATED` evidence cannot emit `PROMOTE` or any production write.
14. Produce an immutable, exportable decision receipt.
15. Provide a local review surface with no live write capability.
16. Keep existing Adjacency brand-safety contracts and G0-G6 behavior unchanged.

### P1 functional requirements

1. Record a bounded set of live Imagine calls after a cost and credential review.
2. Support up to three reference images where the selected model and endpoint permit it.
3. Add provider file-ID reuse to avoid repeated input upload.
4. Add read-only aggregate outcome ingestion with tenant and campaign isolation.
5. Add an authorized experiment-assignment adapter in shadow mode.
6. Add calibrated predicted-response input while keeping it separate from observed response.
7. Run mechanism and learner sensitivity with convergence diagnostics.
8. Add `APPROVE_FOR_DRAFT` with a human authorization service.
9. Add dashboards for lineage, cost, gates, outcomes, experiments, and overrides.
10. Implement export and deletion for tenant-owned briefs, assets, outcomes, and receipts.

### P2 functional requirements

1. Draft-only X Ads integration after internal API review.
2. Display-only randomized creative experiments with ranking frozen.
3. Signal-aware experiments only after separate authorization and rollback proof.
4. Sequential one-axis optimization across multiple rounds.
5. Staged upgrade from standard image to quality image and, only when justified, video.
6. Enterprise controls for retention, regional processing, roles, and audit export.
7. Optional automated promotion only after end-to-end causal evidence and a separate launch review.

### Non-functional requirements

#### Correctness

- Deterministic contracts and gate code must receive complete line and branch coverage.
- Derived metrics must be recomputable from immutable inputs.
- Every admitted decision must have one complete receipt.
- Every action must be idempotent under the same tenant and request key.

#### Reliability

- Provider timeout, malformed response, temporary-URL failure, outcome staleness, and partial joins have specified non-promoting outcomes.
- Retries are bounded and do not multiply paid generation after an ambiguous success.
- Queue backpressure stops new generation before it drops receipts or outcomes.

#### Security and privacy

- Tenant authorization applies to every object and join.
- Credentials stay in secret storage and out of request hashes, logs, and fixtures.
- User-level behavior is not exposed to the creative optimizer in the planned scope.
- Cohort minimums, retention, deletion, and training use require approval before restricted data.

#### Cost

- Each campaign has call, image, quality-tier, wall-clock, and dollar caps.
- Exact provider cost is stored when returned; configured-price estimates are labeled estimates.
- Duplicate checks and low-cost screening occur before quality or video upgrades.

#### Explainability

- Free-form rationale is display-only.
- Decisions derive from typed evidence and deterministic gates.
- Every human override has a reason code and actor.

#### Compatibility

- The new package supports Python 3.12 and 3.13 under the current project constraints.
- The deterministic core imports without model, media, UI, or workflow dependencies.
- The public Adjacency API and gate codes remain backward compatible.

## 5. Design and user experience

### Core workflow

1. Create a campaign brief.
2. Upload or select one approved base image.
3. Choose one mutation axis and two to four levels.
4. Review locked attributes and the generation budget.
5. Generate or replay the family.
6. Inspect lineage, visual differences, moderation status, and cost.
7. Admit eligible variants to a small approved test.
8. Ingest aggregate outcomes after the declared window.
9. Review signal uncertainty and auction sensitivity separately.
10. Receive a next action and complete receipt.

### Required screens

- Brief compiler: goal, audience contexts, base asset, mutable axis, locked attributes, and budget.
- Family view: parent and children, the one declared change, hashes, cost, and status.
- Evidence view: aggregate outcomes, uncertainty, data window, and evidence class.
- Sensitivity view: score distance, boundary crossings, assumptions, and learner disagreement.
- Decision view: final action, stable gate codes, human-review destination, and exported receipt.

### Empty and failure states

| Condition | User-visible result | System action |
|---|---|---|
| No base asset | Brief incomplete | Do not call provider |
| More than one mutation axis | Controlled-family violation | Reject or require a new family |
| Provider moderation rejects output | Output unavailable | Record terminal rejection; do not bypass |
| Provider timeout with unknown completion | Ambiguous generation | Hold; reconcile by idempotency key before retry |
| Temporary URL expired | Asset unavailable | Hold; never admit without verified bytes |
| Duplicate output | Duplicate | Stop paid escalation for that asset |
| No outcomes | Not enough information | `HOLD` |
| Stale or partial outcomes | Evidence incomplete | `HOLD` or `REVIEW` |
| Simulation learners disagree | Assumption-sensitive | `REVIEW`; no robust economic claim |
| Any production-write authorization missing | Write blocked | Keep draft or stop |

## 6. Technical considerations

### Proposed integration boundary

Create `src/adjacency/imagine_signal/` as a parallel bounded context. Reuse stable hashing, fixture replay, human-review interfaces, and quality policy by composition. Do not add creative states to the current brand-safety `Action` enum and do not reuse existing G0-G6 identifiers.

### External dependencies

- xAI Imagine image generation and editing endpoints.
- xAI model and billing access confirmed through the API Console.
- Aggregate outcome and experiment adapters, both unavailable in the public prototype and represented by protocols.
- Internal X Ads details only for later shadow and experimental phases.

### Key design risks

- Controlled prompts may still alter more than the declared visual attribute.
- Selected winners may reflect noise rather than a reusable effect.
- Predicted CTR may be miscalibrated or change after deployment.
- Auction sensitivity may reverse under different bidder dynamics.
- Publisher revenue may rise while advertiser utility, participation, or user experience worsens.
- Provider model aliases and prices may change.
- Temporary media URLs and private brand assets require careful storage behavior.

The controls and stop rules are specified in the technical, evaluation, and operations documents.

## 7. Phased implementation

### Phase 0: specification and deterministic skeleton

Deliver contracts, gates, state machine, synthetic fixtures, paper-linked simulator, receipts, and complete deterministic tests. No network and no production data.

Exit gate: all P0 deterministic invariants pass; `git diff --check`, lint, tests, coverage, secret scan, and fixture replay succeed.

### Phase 1: replayed Imagine family

Add the provider request contract, local blob store, recorded response metadata, and a frozen family of one base plus controlled children. Continue to replay by default.

Exit gate: the same request resolves to the same fixture and media hash; no secret or temporary URL is required for replay.

### Phase 2: bounded live recording

Confirm API access, billing, model availability, rate limit, and a strict dollar cap. Record a small non-sensitive demo family.

Exit gate: cost reconciles, model and moderation metadata are present, every output byte is hashed, and replay passes with the credential removed.

### Phase 3: offline outcome and sensitivity demo

Join synthetic or frozen aggregate outcomes, compute uncertainty, run paired sensitivity, and show an evidence-capped decision receipt.

Exit gate: no simulated result can produce a production action or causal wording.

### Phase 4: read-only internal shadow

Requires named owners, approved data contract, privacy and security review, outcome quality thresholds, dashboards, and kill switches. No publishing, spend, or ranking change.

### Phase 5: draft beta and controlled experiments

Add human-approved draft actions, then run display-only randomization. Signal-aware randomization is a separate later gate.

### Phase 6: limited production consideration

Requires end-to-end randomized evidence, approved SLOs, countermetric health, incident ownership, deletion support, rollback drill, and fresh sign-offs.

## 8. Open questions

1. Which user and one mutation axis define the hackathon demo?
2. What does the account's current SuperGrok usage page allow for API use, and what does the API Console show for the team?
3. Which Imagine model should be primary in each stage: standard for exploration or quality for final candidates?
4. Which exact response metric is primary for the first approved test?
5. What is the randomization unit and measurement window?
6. Which aggregate outcome fields can be used without raw user-level data?
7. What production scoring and billing rules are in scope for internal review?
8. What signal magnitude is worth acting on after uncertainty and multiple testing?
9. What advertiser, participation, and user harm margins block advancement?
10. Who owns the product, auction-science review, security review, privacy review, SRE, and final go or no-go decision?
11. What retention and deletion rules apply to confidential brand assets and generated media?
12. Is ImagineSignal an acceptable product name after legal and trademark review?

## 9. Appendix

### Decision vocabulary

| Action | Meaning in MVP | Side effect |
|---|---|---|
| `KEEP` | The current control remains the reference | None |
| `EDIT` | Prepare one new controlled mutation proposal | Draft only |
| `TEST` | Candidate may enter an approved experiment | No automatic assignment or publish |
| `HOLD` | Wait for complete or fresh evidence | None |
| `REVIEW` | A person must resolve an ambiguity or gate conflict | Review queue only |
| `STOP` | End generation or testing for this family | Cancel future planned work; preserve evidence |

`PROMOTE`, `APPROVE_FOR_DRAFT`, `APPROVE_FOR_PUBLISH`, `QUALITY_UPGRADE`, and `VIDEO_UPGRADE` are reserved for later phases with explicit contracts.

### Non-goals

- Auction-floor or reserve optimization.
- Live bid, budget, pacing, or targeting changes.
- Production inverse value inference.
- Autonomous campaign management.
- Cross-advertiser private-outcome learning.
- Replacement of provider moderation or existing X Ads enforcement.
- A general trust-and-safety benchmark.
- Model-kernel or GPU-level image-generation acceleration.
- Claims based on untracked aesthetic preference alone.

### Source links

- [xAI Imagine overview](https://docs.x.ai/developers/model-capabilities/imagine)
- [xAI image generation](https://docs.x.ai/developers/model-capabilities/images/generation)
- [xAI image editing](https://docs.x.ai/developers/model-capabilities/images/editing)
- [xAI pricing](https://docs.x.ai/developers/pricing)
- [Advancing Ad Auction Realism](https://arxiv.org/abs/2307.11732)
- Existing repository: `README.md`, `ARCHITECTURE.md`, `QUALITY.md`, `src/adjacency/contracts.py`, `src/adjacency/gates.py`, `src/adjacency/fixtures.py`, and `src/adjacency/xai.py`.

