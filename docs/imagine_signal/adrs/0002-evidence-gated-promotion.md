# ADR 0002: Cap recommendations by evidence class

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-08-05 |
| Author | Arun Sharma |
| Deciders | Product, experimentation, Ads science, finance, TBD |
| Reviewers | Engineering, security, privacy, advertiser integrity |

## Context

ImagineSignal combines several forms of information: design proposals, unit tests, frozen replay, auction simulation, read-only shadow estimates, and eventually randomized experiments. These forms do not support the same action or claim.

The supplied auction paper is valuable for simulation design, but it does not establish a causal creative or publisher-revenue effect. The current Adjacency results validate its own safety-control pattern, not ImagineSignal outcomes.

Without a hard boundary, a persuasive simulation or model rationale could be presented as evidence for live promotion.

## Options considered

### Option A: Use one confidence score for every decision

The optimizer emits a score and a threshold decides whether to promote.

Advantages:

- Simple interface.
- Easy ranking of candidates.

Disadvantages:

- Hides the origin and quality of evidence.
- A high simulated score can outrank weak or missing causal evidence.
- Thresholds are difficult to audit across data sources.

### Option B: Define an evidence ladder with an action ceiling

Each result carries an evidence class. A deterministic gate maps that class to the highest possible action and approved claim vocabulary. Other gates can only reduce the action.

Advantages:

- Simulation cannot silently authorize production.
- Claims stay connected to source artifacts.
- Reviewers can see exactly what new evidence unlocks the next stage.
- Human rationale cannot override the boundary.

Disadvantages:

- More states and receipt fields.
- Slower progression when evidence or ownership is missing.
- Requires claim maintenance when models or mechanisms change.

### Option C: Remove auction sensitivity until production experiments exist

Keep only creative generation and response testing.

Advantages:

- Simplest claim surface.
- Avoids mechanism-model confusion.

Disadvantages:

- Loses the useful research question about score boundaries.
- Provides less guidance about which response deltas deserve costly follow-up.

## Decision

Choose Option B.

Every proposal and receipt carries an `EvidenceClass`. `IS8` enforces the evidence-to-action ceiling. A result labeled `SIMULATED` may justify a controlled non-production test, but cannot authorize publishing, spend, ranking, or a revenue claim.

The MVP omits `PROMOTE`. Its maximum positive action is `TEST`, and that means only "eligible for a separately authorized test."

Observed CTR, predicted CTR, simulated CTR, advertiser spend, attributed purchase value, billed ad revenue, simulated seller revenue, and advertiser utility remain distinct fields.

## Consequences

### Positive

- Claim quality is enforced in code, not only review prose.
- Paper-derived insight can be included without overstating it.
- Every future launch stage has a clear evidence requirement.
- An audit receipt can explain why an attractive candidate was held.

### Negative

- Some users may find `HOLD` or `REVIEW` conservative.
- Evidence labels and claim expiry require operational ownership.
- A human approver cannot simply waive causal evidence.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Evidence label forged or stale | Derive from source contracts and expire on version changes |
| Human override exceeds ceiling | Separate authorization gate cannot exceed environment mode or evidence policy |
| Simulation cherry-picked | Pre-register scenarios and report all configured learners |
| Revenue terms conflated | `RevenueKind` enum and finance review |

## Implementation notes

Implement the evidence table as a total, pure mapping. Add property tests that every evidence and proposed-action pair produces an allowed final action. Store both proposed and final action in the receipt.

## Review trigger

Revisit before adding `APPROVE_FOR_DRAFT`, `APPROVE_FOR_PUBLISH`, ranking-signal export, or automated promotion.

