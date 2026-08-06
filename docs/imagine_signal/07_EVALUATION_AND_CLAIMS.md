# ImagineSignal evaluation, experiments, and claims

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed evaluation protocol |
| Author | Arun Sharma |
| Required approvers before live experiment | Product, experimentation, Ads engineering, Ads science, privacy, security, SRE, finance |
| Date | 2026-08-05 |

## 1. Evaluation principle

The evaluation ladder prevents a promising simulation from silently becoming a production revenue statement. Advancement requires new evidence, not a change in wording.

```mermaid
flowchart LR
    E0["E0: deterministic correctness"] --> E1["E1: frozen offline replay"]
    E1 --> E2["E2: auction sensitivity simulation"]
    E2 --> E3["E3: read-only shadow replay"]
    E3 --> E4["E4: display-only randomized test"]
    E4 --> E5["E5: signal-aware randomized test"]
    E5 --> E6["E6: controlled production rollout"]
```

Each stage has an evidence label, permitted claim, and stop rule.

## 2. Primary product estimand

The first product question is generation efficiency:

> For an admitted campaign brief, how much reusable, decision-quality creative evidence does ImagineSignal produce per generation dollar compared with an equally budgeted unstructured generation workflow?

This requires a pre-registered control workflow. It is not enough to compare ImagineSignal with an intentionally weak or differently funded baseline.

Primary offline and shadow measures:

- Qualified creative yield.
- Cost per qualified creative.
- Time to testable family.
- Duplicate paid-output rate.
- Percent of quality-tier calls assigned to eventual test candidates.
- Percent of families with exactly one declared change.
- Receipt and lineage completeness.

## 3. Later causal estimands

### Creative-response estimand

Among already-won impressions with allocation and price held fixed, estimate the causal effect of displaying the controlled variant rather than the baseline on the pre-registered response metric.

This isolates user response to the creative. It does not estimate auction reallocation.

### End-to-end ads estimand

Within an authorized traffic slice where the calibrated creative signal may affect ranking, estimate the causal effect of the complete ImagineSignal treatment on billed revenue per eligible impression.

This must include advertiser, participation, fill, and user countermetrics. It cannot be inferred from clicks or advertiser spend alone.

## 4. Evidence ladder

### E0: deterministic correctness

Required evidence:

- Contract validation and stable hash vectors.
- Lineage, tenant, budget, outcome, and evidence-ceiling gates.
- Hand-checked arithmetic.
- Synthetic faults.
- Complete line and branch coverage for contracts and gates.
- Secret-free request and response fixture tests.
- Network-disabled replay.

Permitted claim:

> The controller detects the tested structural faults and enforces the specified action ceiling.

Not permitted:

> ImagineSignal improves creative, campaign, or revenue outcomes.

### E1: frozen offline benchmark

Required evidence:

- Frozen campaign briefs and brand constraints.
- Frozen base and generated assets.
- Frozen synthetic or authorized historical aggregate outcomes.
- Stable data, media, configuration, and code hashes.
- Same-budget baseline.
- Repeat runs and artifact-backed metrics.
- Exact provider-cost replay or clearly labeled estimated cost.

Permitted claim:

> On the named frozen benchmark, ImagineSignal changed generation allocation and achieved the reported evidence yield or cost result.

The claim expires when the benchmark, model, prompt compiler, or cost schedule changes.

### E2: mechanism-sensitivity simulation

Required evidence:

- Fixed-bid primary analysis.
- Common random numbers for baseline and variant.
- Signal sweep around zero.
- Single-query and multi-query settings.
- First-price, second-price, and paper-linked soft-floor scenarios where relevant.
- Hedge and EXP3-IX reported together for adaptive modes.
- Convergence diagnostics.
- Multiple plausible value and CTR settings.
- Uncertainty, advertiser utility, fill, and participation metrics.

Permitted claim:

> Under the specified scenario and bidder model, the stated creative-signal perturbation changed simulated outcomes by the reported amount.

Not permitted:

> The variant increases X revenue.

### E3: read-only logged or shadow replay

Required evidence for a publisher-revenue estimate:

- Candidate set and eligibility.
- Bids and scoring inputs.
- Pricing inputs, winner, and actual billed revenue.
- Budgets and pacing state.
- Experiment or logging-policy support.
- Held-out model validation.
- No production writes.

Permitted claim:

> Under the named replay assumptions and support conditions, the estimated counterfactual effect is the reported value.

If complete auction state is unavailable, report advertiser-side outcomes only and block the publisher-revenue replay.

### E4: display-only randomized test

The experiment randomizes the creative after auction allocation while the winner, ranking score, and auction price remain fixed.

Required evidence:

- Authorized experiment ID and pre-registration.
- Stable assignment and exposure logs.
- Same winner and price by construction.
- Actual outcomes and billed-revenue behavior for the already-won impressions.
- Cluster-aware analysis at the assignment unit.
- Multiple-testing policy for more than one variant.
- Advertiser and user guardrails.
- Sample-ratio-mismatch checks.

Permitted claim:

> Among already-won impressions in the authorized test, the controlled creative variant causally changed the specified response or billing metric by the reported amount.

The claim does not include auction reallocation.

### E5: signal-aware randomized test

The calibrated creative signal can affect ranking in a tiny, explicitly authorized slice.

Required evidence:

- Separate launch and experiment authorization.
- Predeclared unit, estimand, population, MDE, power, and duration.
- Budget and pacing isolation across arms.
- Actual billed revenue and allocation logs.
- Treatment-assignment integrity.
- Short-run and adaptive-period estimates.
- Automated harm monitoring and immediate signal kill switch.
- Advertiser ROI, fill, participation, concentration, and user guardrails.
- Tested rollback.

Permitted claim:

> In the authorized traffic slice, the end-to-end treatment causally changed billed revenue per eligible impression by the reported amount, with the listed guardrail results.

### E6: controlled rollout

Required evidence:

- E5 completed and reviewed.
- Approved SLOs met.
- No unresolved P0 risk.
- Support and on-call ownership.
- Tenant export and deletion tested.
- Rollback drill passed.
- Claim register approved and current.
- Staged expansion with fresh sign-off at each threshold.

## 5. Baselines

Use at least these baselines where applicable:

1. Same-budget unstructured generation: prompts may vary freely, but budget, model access, reviewers, and test allocation match.
2. Human-only controlled design: a strategist specifies one-axis variants without ImagineSignal's optimizer.
3. Uniform generation: equal budget per mutation level.
4. Standard-only model: no quality upgrade.
5. Quality-only model: every candidate uses the quality tier.
6. No duplicate filter.
7. No auction-sensitivity layer.
8. Fixed-bid sensitivity only versus adaptive learner modes.

The baseline must use the same initial brief and base asset. A baseline created from different policy prose or a different budget is invalid.

## 6. Ablations

- Remove lineage admission.
- Allow more than one mutation axis.
- Remove locked-attribute validation.
- Remove duplicate suppression.
- Remove uncertainty and select the highest raw CTR.
- Remove evidence-to-action ceiling.
- Use predicted CTR as if it were observed.
- Report only Hedge or only EXP3-IX.
- Upgrade every variant to quality.
- Remove cost from the next-action score.

These ablations should reveal whether the contribution comes from controlled mutation, evidence discipline, efficiency routing, or favorable assumptions.

## 7. Statistical plan

Before any authorized test, pre-register:

- Primary metric and exact numerator and denominator.
- Assignment unit.
- Eligible population.
- Control and treatment definition.
- Attribution and outcome windows.
- Minimum detectable effect.
- Power and sample requirement.
- Number of variants and multiple-testing control.
- Stopping rule and maximum duration.
- Missing-event and delayed-conversion treatment.
- Cluster and repeated-exposure handling.
- Guardrail harm margins.
- Estimator and confidence or credible interval.
- Whether analysis is intent-to-treat, treatment-on-treated, or both.

Do not repeatedly inspect ordinary confidence intervals and stop when a favorable value appears. Use the approved experimentation platform's sequential method or a fixed-horizon analysis.

For multi-variant selection, hold back an independent confirmation sample or use a pre-approved hierarchical or multiple-comparison method. The selected best observed variant is otherwise biased upward.

## 8. Metrics

### Generation and workflow

```text
qualified_creative_yield = admitted_test_creatives / generated_creatives
cost_per_qualified_creative = total_reconciled_generation_cost / admitted_test_creatives
duplicate_paid_output_rate = paid_duplicates / paid_outputs
quality_precision = eventual_qualified_quality_outputs / quality_outputs
lineage_completeness = complete_lineage_assets / admitted_assets
```

If a denominator is zero, report the metric as unavailable, not zero.

### Response

- Impressions.
- Qualified impressions, if defined by the source.
- Clicks and CTR.
- URL clicks.
- Conversions and conversion rate.
- Hide, report, negative-feedback, or session effects where available.
- Creative fatigue by exposure count and time.

### Advertiser economics

- Advertiser spend.
- Cost per click.
- Cost per acquisition.
- Attributed purchase value.
- ROAS, only when value and spend semantics are valid.
- Simulated or measured advertiser utility, clearly separated.

### Publisher and market health

- Billed ad revenue per eligible impression, only from an authorized source.
- Fill.
- Query coverage.
- Small-advertiser participation.
- Advertiser concentration.
- Allocation changes.
- Simulated seller revenue, labeled as simulation.

## 9. Synthetic fault suite

Inject at least these faults:

- Missing parent.
- Parent and child from different tenants.
- Lineage cycle.
- Multiple declared mutation axes.
- Locked logo, claim, or product identity changed.
- Request hash attached to different media.
- Corrupt media bytes or false dimensions.
- Provider moderation rejection marked as accepted.
- Unknown provider cost treated as zero.
- Duplicate outcome event.
- Outcome outside the measurement window.
- Outcome from another campaign or experiment arm.
- Stale or partial outcome snapshot.
- Simulated result mislabeled as measured.
- Predicted CTR stored in an observed CTR field.
- Non-converged learner reported as valid.
- One unfavorable learner omitted.
- Action above the evidence ceiling.
- Human approval attached to another receipt.
- Concurrent duplicate execution.
- Secret in request or response fixture.

Every injected fault must map to a stable gate or adapter error code.

## 10. Advancement and stop rules

Stop the current stage and do not advance when:

- A deterministic invariant or core coverage gate fails.
- A fixture contains a secret, signed URL, or confidential asset.
- Assignment, outcome, cost, lineage, or receipt completeness misses the approved threshold.
- The minimum detectable effect is infeasible for the allowed sample or duration.
- The response or economic effect changes sign across plausible mechanisms or learners.
- A learner fails convergence or stability criteria.
- Budget or pacing spillovers contaminate the experiment.
- Advertiser ROI, fill, participation, concentration, or user guardrails cross the approved harm boundary.
- Publisher-revenue evidence lacks actual billed revenue.
- The creative signal is not isolated from selection or ranking changes.
- A rollback or kill switch fails its drill.
- An owner, on-call, privacy, security, or finance sign-off is missing for the requested stage.

## 11. Claim register

Every external or executive-facing claim needs:

- Claim ID and exact wording.
- Product and model version.
- Evidence class.
- Dataset and population.
- Metric definition, numerator, and denominator.
- Statistical method and interval.
- Caveats and expiration trigger.
- Owner and approver.
- Source artifact.
- Disallowed paraphrases.

### Initial approved wording

| Claim ID | Evidence required | Approved wording |
|---|---|---|
| `IS-C001` | Current design packet | "ImagineSignal is a proposed controlled creative testing and promotion layer for Grok Imagine." |
| `IS-C002` | Current repository inspection | "The existing Adjacency project provides reusable patterns for immutable contracts, deterministic gates, and replay-first external calls." |
| `IS-C003` | E0 tests | "The controller detects the tested lineage, evidence, budget, and claim-admission faults." |
| `IS-C004` | E1 artifact | "On the named frozen benchmark, the system produced the reported qualified-creative yield and generation cost." |
| `IS-C005` | E2 artifact | "Under the specified auction scenario and bidder model, the creative-signal perturbation changed the reported simulated outcome." |
| `IS-C006` | E4 authorized test | "Among already-won impressions in the named experiment, the variant causally changed the specified response by the reported amount." |
| `IS-C007` | E5 authorized test | "In the named traffic slice, the end-to-end treatment causally changed billed revenue per eligible impression by the reported amount, with the listed guardrails." |

### Prohibited wording without end-to-end randomized evidence

- "ImagineSignal increases X revenue."
- "Better Grok images produce higher auction revenue."
- "A small creative signal creates revenue lift."
- "Soft floors monetize ImagineSignal."
- "Inferred bids reveal true advertiser willingness to pay."
- "Controlled creative mutation causally improves CTR."
- "The optimizer improves advertiser and publisher outcomes together."
- "The result generalizes to all queries or advertisers."
- "The existing Adjacency results validate ImagineSignal."
- "The selected best variant is an unbiased winner."

## 12. Evidence artifact layout

```text
artifacts/imagine_signal/
  manifests/
  deterministic_faults/
  frozen_families/
  outcome_snapshots/
  auction_sensitivity/
  receipts/
  reports/
```

Every report value must name a committed artifact containing its inputs, numerator, denominator, or measured call record. Console output alone is not evidence.

