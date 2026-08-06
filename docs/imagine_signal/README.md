# ImagineSignal offline MVP and production review packet

| Field | Value |
|---|---|
| Version | 0.2 |
| Status | Offline MVP implemented and verified; production no-go |
| Author | Arun Sharma |
| Prepared | 2026-08-05 |
| Next review | Before any live API recording or production-data access |
| Working name | ImagineSignal, pending product and trademark review |

ImagineSignal is a controlled creative testing and promotion layer for Grok Imagine. It creates a family of ad images where one declared visual choice changes at a time, records the lineage and generation cost, measures downstream outcomes, and recommends the next justified action. An optional Auction Sensitivity Layer tests whether a measured creative signal could matter near an ad-ranking boundary. Deterministic Adjacency-style gates control what the system is allowed to claim or recommend.

This directory contains a production-oriented feature specification and an implemented offline MVP. It is not a claim that the feature is production ready. All current execution evidence comes from frozen synthetic replay and explicit simulation. The current recommendation is:

- `GO` for review and continued use of the local frozen-replay MVP.
- `CONDITIONAL_GO` for design work toward a read-only internal shadow, subject to named owners and approved aggregate data access.
- `NO_GO` for autonomous publishing, campaign spend changes, ranking-signal export, auction changes, or external revenue claims.

## Five-minute review path

1. [Decision cover](00_DECISION_COVER.md): current recommendation, enabled surfaces, disabled surfaces, and blockers.
2. [Plain-language explanation](01_PLAIN_EXPLAINER.md): the project without technical jargon, plus a broad-audience diagram and talk track.
3. [Product requirements document](02_PRD.md): users, requirements, success measures, non-goals, and phased delivery.
4. [System design](03_SYSTEM_DESIGN.md): components, data flow, trust boundaries, failure paths, and deployment modes.
5. [Technical specification](04_TECHNICAL_SPEC.md): proposed package layout, immutable contracts, gates, state machine, and service API.
6. [xAI integration](05_XAI_INTEGRATION.md): verified Imagine API surface, model choices, cost controls, SuperGrok guidance, and replay design.
7. [Auction-science model card](06_AUCTION_SCIENCE_MODEL_CARD.md): the exact contribution and limitations of the supplied auction paper.
8. [Evaluation and claims](07_EVALUATION_AND_CLAIMS.md): evidence ladder, experiments, metrics, stop rules, and approved wording.
9. [Security, privacy, and operations](08_SECURITY_PRIVACY_OPERATIONS.md): threat model, data governance, SLO template, observability, rollout, rollback, and incidents.
10. [Implementation plan](09_IMPLEMENTATION_PLAN.md): ordered engineering slices with files, tests, dependencies, and acceptance gates.
11. [Review checklist](10_REVIEW_CHECKLIST.md): reviewer matrix, risk register, open decisions, and sign-off record.
12. [August 6 session handoff](11_AUG6_SESSION_HANDOFF.md): historical implementation handoff, retained for provenance and superseded for current status.
13. [Offline MVP implementation status](12_IMPLEMENTATION_STATUS.md): completed scope, deterministic demo evidence, exact reproduction, production blockers, and review order.
14. [Claude handoff](13_CLAUDE_HANDOFF.md): current cross-model checkpoint, exact worktree state, evidence identifiers, stop conditions, and continuation routing.
15. [Claude resume prompt](14_CLAUDE_RESUME_PROMPT.md): paste-ready bootstrap prompt for a fresh local Claude session.

## Architectural decisions

- [ADR 0001: isolate ImagineSignal in a parallel domain package](adrs/0001-parallel-domain.md)
- [ADR 0002: cap recommendations by evidence class](adrs/0002-evidence-gated-promotion.md)
- [ADR 0003: make replay the default for the Imagine adapter](adrs/0003-replay-first-imagine-adapter.md)

## Evidence legend

Every result, dashboard value, and claim must carry one of these labels:

| Label | Meaning | Highest allowed conclusion |
|---|---|---|
| `PROPOSED` | Design exists only in this packet | Discuss the design |
| `IMPLEMENTED` | Code exists but has not passed the required tests | Describe the implementation |
| `UNIT_TESTED` | Deterministic behavior passed repository tests | Claim the tested behavior only |
| `FROZEN_REPLAY` | A repository-backed, hashed benchmark reproduced | Claim the replayed result on that benchmark |
| `SIMULATED` | An auction scenario produced a modeled outcome | State the scenario-dependent simulated result |
| `SHADOW_ESTIMATE` | Read-only production logs were evaluated | State an estimate with assumptions and uncertainty |
| `RANDOMIZED_DISPLAY_ONLY` | Creative changed after allocation in an authorized experiment | Claim a causal response effect among already-won impressions |
| `RANDOMIZED_END_TO_END` | Creative signal could affect allocation in an authorized experiment | Claim a causal effect for the tested traffic slice |
| `SCALED_PRODUCTION` | The effect persisted through approved rollout | Claim only the measured production scope |

Simulation, replay, shadow estimates, and randomized results must never appear in one unlabeled results table.

## Target product boundary

The target feature may support the capabilities below after the required approval. The current offline MVP only exercises synthetic fixture replay, aggregate synthetic outcomes, simulation, and local decision receipts.

ImagineSignal may:

- Generate or edit draft images through Grok Imagine.
- Change one declared creative attribute at a time.
- Record parent-child lineage, hashes, provider metadata, latency, and cost.
- Ingest aggregate outcomes from an approved source.
- Estimate creative-response signals with uncertainty.
- Simulate auction sensitivity under explicit assumptions.
- Recommend `KEEP`, `EDIT`, `TEST`, `HOLD`, `REVIEW`, or `STOP`.
- Produce an immutable decision receipt.

ImagineSignal may not in the first release:

- Publish an ad.
- Change a campaign budget, bid, target, reserve, floor, or auction mechanism.
- Export a ranking signal to a live auction.
- Treat predicted CTR as observed CTR.
- infer willingness to pay as fact.
- Replace existing content, ads-policy, brand-safety, or legal review.
- Claim that Grok Imagine or ImagineSignal increases X revenue.

## Existing repository assets reused

The implementation is designed to reuse these proven patterns without changing their current public semantics:

- Immutable Pydantic contracts and stable hashes from `src/adjacency/contracts.py`.
- Pure fail-closed gate results and stable codes from `src/adjacency/gates.py`.
- Request-scanned, content-addressed replay from `src/adjacency/fixtures.py`; Imagine recording must add response scanning and binary-asset validation.
- Recorded xAI transport conventions from `src/adjacency/xai.py`.
- Human-review protocol isolation from `src/adjacency/hitl.py`.
- Asymmetric coverage and fixture-replay policy from `QUALITY.md`.

The existing brand-safety `Action`, `Verdict`, and G0-G6 codes remain unchanged. ImagineSignal gets a separate namespace and separate gate codes because creative promotion and inventory serving are different decisions.

## Source boundary

The supplied paper supports an auction-sensitivity research layer. It does not establish a live creative or publisher-revenue effect. Official xAI documentation confirms that the Imagine API currently supports image generation, image editing, multiple images, aspect-ratio and resolution controls, response moderation metadata, concurrent calls, and Files API integration. Exact links and the date-checked interpretation are in [the xAI integration note](05_XAI_INTEGRATION.md).
