# Auction Sensitivity Layer model card

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed research component, simulation only |
| Author | Arun Sharma |
| Primary source | Chen, Nabi, and Siniscalchi, "Advancing Ad Auction Realism: Practical Insights and Modeling Implications" |
| Source copy reviewed | `/Users/arunsharma/Downloads/2307.11732v2.pdf` |
| Public source | [arXiv:2307.11732](https://arxiv.org/abs/2307.11732) |
| Date reviewed | 2026-08-05 |

## 1. Purpose

The Auction Sensitivity Layer asks a bounded question:

> Given an explicitly measured or hypothesized change in an ad's click response, under what stated auction assumptions could that small signal change allocation, simulated seller revenue, or simulated advertiser utility?

It does not optimize the auction. It does not choose floors, reserves, bids, budgets, pacing, or targeting. It does not claim to reproduce X's production auction. Its job is to expose sensitivity and assumption dependence before a team spends more generation or experiment budget.

## 2. Why it belongs next to ImagineSignal

Controlled creative mutation identifies a possible response change. Whether that change matters economically depends on where the ad sits relative to competing scores. A small signal can matter near a boundary and have no allocation effect far from it.

This layer creates a useful bridge:

```text
controlled visual change
-> observed or hypothesized response delta
-> score-boundary sensitivity
-> evidence-gated decision about the next test
```

The bridge is conditional. A visual change does not automatically cause a response change, and a response change does not automatically cause revenue lift.

## 3. Source-paper model

The paper studies repeated, single-slot ad auctions with a finite set of query contexts. Each bidder has query-dependent value per click and click-through rate. A bidder chooses one bid and a targeting clause before the query is realized.

For bidder `i` in query `q`, the paper's score is:

```text
s_i(q) = b_i * CTR_i(q)
```

The highest eligible score wins. The bidder's expected payoff depends on click-through rate, value per click, and price per click.

The paper represents bidder adaptation with two online-learning algorithms:

- Hedge, a full-information learner that uses rewards for all actions.
- EXP3-IX, a partial-information learner that learns from the chosen action's reward.

These are modeling assumptions. They are not evidence that real advertisers use either algorithm.

## 4. Result that motivates robustness checks

In the paper's symmetric multi-query example, the ordering of mechanisms changes with the bidder-learning model.

| Learner | First price | Second price | Soft floor 0.65 |
|---|---:|---:|---:|
| EXP3-IX | 0.0830 | 0.0509 | 0.0813 |
| Hedge | 0.0691 | 0.0857 | 0.0741 |

These are the paper's simulated mean revenues for its specified scenario, horizons, and averaging scheme. They are not ImagineSignal results and not X production measurements.

The practical lesson is not that one mechanism wins. The practical lesson is that a favorable revenue conclusion can reverse under another plausible bidder-behavior model. ImagineSignal must display both and treat sign or ranking disagreement as a robustness failure.

## 5. Conceptual integration

### Baseline and variant

For a controlled family, define:

- `c_base(q)`: the estimated true click response for the baseline in context `q`.
- `c_variant(q)`: the estimated true click response for the variant.
- `p_base(q)`: the predicted CTR used by the ranking system, if available.
- `p_variant(q)`: the predicted CTR used by the ranking system, if available.

`c` and `p` are different objects. A real user response may change before the ranking model recognizes it. A ranking-model estimate may also be miscalibrated.

### Fixed-bid sensitivity

The MVP holds bids, competitors, queries, and random draws fixed. It changes only the focal creative signal. It measures:

- Score-distance change.
- Probability of crossing the winning boundary.
- Allocation-change rate.
- Simulated seller-revenue change.
- Simulated focal-advertiser utility change.
- Results by query context.

Fixed-bid sensitivity is the clearest first demonstration because it isolates the creative signal. It is not a long-run equilibrium claim.

### Adaptive-bidder sensitivity

Hedge and EXP3-IX are later research modes. Baseline and variant runs use common random numbers, identical initial conditions, predeclared horizons, and convergence diagnostics. The result report must include every configured learner, including unfavorable or non-converged runs.

## 6. Required scenario disclosure

Every scenario must state:

- Auction unit and number of slots.
- Billing basis.
- Scoring rule.
- Pricing mechanism.
- Floor or reserve behavior.
- Budget and pacing behavior.
- Candidate eligibility and targeting semantics.
- Query representation and probabilities.
- Bidder types, values, CTRs, and bid grid.
- Whether CTR is true, predicted, synthetic, replayed, or measured.
- Bidder adaptation model.
- Horizon, burn-in, seeds, and repetitions.
- Tie breaking.
- Known departures from the scoped production system.
- Data origin and permitted claim.

If any field is unknown, the scenario is a hypothetical research case and cannot support a production recommendation.

## 7. Paper-to-product contribution map

| Paper contribution | ImagineSignal use | What is not transferred |
|---|---|---|
| Query-dependent value and CTR | Evaluate creative signal by context | No claim that the chosen contexts match production queries |
| Bid times CTR score | Explain why small response changes can matter near score boundaries | No claim that this is the complete current X scoring rule |
| Targeting clauses | Show that broad and narrow contexts can interact | No automatic targeting change |
| Hedge and EXP3-IX | Sensitivity to bidder learning assumptions | No claim that advertisers follow either learner |
| Soft-floor simulations | Demonstrate mechanism-dependent results | No floor or reserve optimization |
| Inverse value inference | Caveat that latent values depend on mechanism assumptions | No production willingness-to-pay inference |

## 8. Known departures and limitations

The supplied paper:

- Uses one slot.
- Uses finite queries with stationary probabilities.
- Has a fixed finite bid grid.
- Lets bidders choose a bid and targeting clause before query realization.
- Uses independently simulated bidder learning.
- Does not model a complete production candidate, pacing, budget, quality, policy, or auction stack.
- Does not generate or compare ad creatives.
- Does not run a randomized creative experiment.
- Does not establish that a small creative change affects true or predicted CTR.
- Does not measure causal publisher-revenue lift.
- Illustrates production inverse inference with aggregate bids for two queries while setting CTR to one.

The production aggregate example is evidence that the inference procedure can be applied under simplifying assumptions. It is not validation that inferred values equal true advertiser willingness to pay.

## 9. Input requirements

### MVP synthetic input

- One campaign.
- Two query or audience contexts.
- One baseline and up to four controlled variants.
- One creative mutation axis.
- Explicit focal and competing bids.
- Explicit CTR matrices and values.
- One-slot first-price and second-price settings.
- Optional soft-floor setting for paper reproduction only.
- Fixed-bid primary mode.
- Paired seeds.

### Shadow input, if later approved

Meaningful publisher-revenue replay needs candidate sets, bids, scoring inputs, pricing inputs, winners, prices, billed revenue, budgets, pacing, experiment assignment, and counterfactual support. Public advertiser analytics do not supply this complete state.

If those inputs are unavailable, stop at advertiser-side outcomes or a labeled conditional simulation.

## 10. Output contract

Every result includes:

- Scenario hash and code version.
- Baseline and variant evidence hashes.
- Data origin.
- Mechanism and bidder model.
- Seed set and common-randomness ID.
- Convergence or stability diagnostics.
- Score-distance distribution.
- Boundary-crossing and allocation-change rates.
- Simulated seller revenue, explicitly labeled.
- Simulated advertiser utility, explicitly labeled.
- Fill, participation, and concentration where the scenario supports them.
- Uncertainty and repetitions.
- Known limitations.
- Allowed claim sentence.
- Disallowed broader claims.

## 11. Validation plan

### Arithmetic tests

- Hand-computed two-bidder score, winner, price, revenue, and utility cases.
- Explicit tie behavior.
- Zero CTR and zero bid behavior.
- Query-targeting eligibility.
- First-price, second-price, and soft-floor pricing branches.

### Reproduction tests

- Reproduce the paper's simple revenue-equivalence sanity case within declared tolerance.
- Reproduce the direction and approximate values of the paper's multi-query tables using independently written code and fully recorded configuration.
- Do not copy or claim reuse of an unavailable paper repository.

### Robustness tests

- Multiple seeds and common random numbers.
- Signal sweep around zero.
- Fixed bids, Hedge, and EXP3-IX.
- Multiple plausible value and CTR matrices.
- Longer horizons with convergence diagnostics.
- Single-query and multi-query cases.
- Alternative tie rules and bid grids.
- Removal of one learner to show how cherry-picking changes the conclusion.

## 12. Admission rules

The layer cannot produce a robust economic recommendation when:

- The actual scoped scoring or pricing behavior is unknown.
- The effect changes sign across plausible mechanisms or learners.
- A configured learner fails the predeclared convergence or stability rule.
- The model omits a production feature likely to reverse the result.
- Only an in-sample inverse fit exists.
- Aggregate bids are treated as identified true values.
- Predicted CTR is substituted for observed CTR without disclosure.
- The creative signal comes from the same data used to choose the winning variant without selection-bias correction.
- Advertiser utility, participation, fill, or user guardrails are absent from a revenue interpretation.

The allowed fallback is `REVIEW` or a statement that the result is scenario-dependent and suitable only for designing a test.

## 13. Prohibited uses

- Selecting or changing a live auction mechanism.
- Optimizing a soft floor or reserve.
- Setting bids, budgets, pacing, or targeting.
- Predicting individual advertiser willingness to pay.
- Reporting simulated seller revenue as billed revenue.
- Claiming general equilibrium or production causality.
- Reporting only the favorable learner.
- Allowing the simulator to publish, spend, or export a ranking signal.

## 14. Model-card maintenance

Expire dependent results when the Imagine model, creative signal estimator, scoring rule, pricing mechanism, targeting behavior, bidder population, query mix, attribution method, or experiment population changes. Preserve the original receipt and issue a new version rather than overwriting it.

