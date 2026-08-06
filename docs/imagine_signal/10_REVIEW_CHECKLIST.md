# ImagineSignal review checklist and sign-off record

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Open for review |
| Author | Arun Sharma |
| Date | 2026-08-05 |
| Current decision | Conditional go for offline implementation; no-go for live writes or auction influence |

## 1. Reviewer instructions

Reviewers should evaluate the exact requested phase, not an imagined future product. Mark each item:

- `PASS`: evidence is present and sufficient for the requested phase.
- `CONDITIONAL`: a named condition, owner, deadline, and fallback are recorded.
- `FAIL`: the phase cannot proceed.
- `N/A`: the capability is structurally absent from the requested phase.

A document, owner promise, or roadmap item does not count as implementation evidence.

## 2. Current evidence and scope audit

| Statement | Status | Evidence or action |
|---|---|---|
| Current Adjacency has immutable typed contracts | Implemented in current repository | `src/adjacency/contracts.py` |
| Current Adjacency has deterministic fail-closed gates | Implemented in current repository | `src/adjacency/gates.py` |
| Current Adjacency replays external JSON calls by default | Implemented in current repository | `src/adjacency/fixtures.py`, with response-scan gap documented |
| Current Adjacency has an Imagine image adapter | Not implemented | Planned PR 4 and PR 5 |
| Current Adjacency has creative lineage or outcome contracts | Not implemented | Planned PR 1 and PR 6 |
| Current Adjacency has X Ads integration | Not implemented | Later phase only |
| Auction paper supports conditional simulation | Source reviewed | Model card and supplied PDF |
| Auction paper proves creative revenue lift | False | Explicitly prohibited claim |
| ImagineSignal is production ready | False | This packet is a proposed specification |
| SuperGrok guarantees production API credits | Unverified | Check account Usage and API Console |

## 3. Offline implementation gate

- [ ] Worktree and existing user changes inspected before editing.
- [ ] Parallel bounded-context ADR accepted.
- [ ] Contracts reject unknown fields and have fixed schema versions.
- [ ] Public canonical hashing added without importing private `_stable_hash`.
- [ ] Parent, root, campaign, and tenant lineage enforced.
- [ ] One mutation axis and locked attributes enforced.
- [ ] IS0 through IS8 are pure and have stable codes.
- [ ] Evidence-to-action ceiling cannot be bypassed.
- [ ] New contracts and gates have complete line and branch coverage.
- [ ] Existing Adjacency tests and gate behavior remain green.
- [ ] Replay works without network and credentials.
- [ ] Missing fixture cannot fall back live.
- [ ] Both request and response fixture metadata are secret scanned.
- [ ] Binary assets are stored by verified digest outside JSON metadata.
- [ ] Unknown cost is distinct from zero cost.
- [ ] Every report value points to an artifact.
- [ ] Simulation and measured outcomes use different fields and labels.
- [ ] No production write client exists in the offline process.

Any unchecked deterministic or boundary item blocks the offline MVP from being called complete.

## 4. Bounded live Imagine recording gate

- [ ] User explicitly authorizes a live recording.
- [ ] Intended xAI team selected in `console.x.ai`.
- [ ] API credits and postpaid limit verified.
- [ ] Required image model shown as enabled.
- [ ] Scoped development key created and stored outside repository and chat.
- [ ] Non-sensitive demo prompt and base asset approved.
- [ ] Call, output, quality-tier, and dollar cap approved.
- [ ] Dated model alias selected for reproducibility.
- [ ] Ambiguous-success retry behavior tested.
- [ ] Output bytes downloaded or decoded immediately and hashed.
- [ ] Moderation, resolved model, request ID, latency, and actual cost recorded.
- [ ] Credential removed and offline replay rerun.
- [ ] Fixture and logs scanned for keys, signed URLs, base64, and confidential content.

If any item fails, remain in fixture mode.

## 5. Shadow gate

- [ ] Product, engineering, data, SRE, security, privacy, and finance owners named.
- [ ] Exact read-only data source and permitted purpose approved.
- [ ] Tenant authorization and isolation tests pass.
- [ ] Data inventory, classification, retention, deletion, and training-use decisions approved.
- [ ] Outcome contract defines source, unit, window, freshness, attribution, and currency semantics.
- [ ] SLO targets, dashboards, alerts, and on-call approved.
- [ ] Generation and outcome-ingestion kill switches tested.
- [ ] No publish, spend, target, bid, floor, reserve, pacing, or ranking write path.
- [ ] Experiment and claim registers exist.
- [ ] Aggregate analytics are not mislabeled as platform revenue.
- [ ] Counterfactual auction claims are blocked when required auction state is unavailable.

## 6. Live experiment gate

- [ ] Experiment owner and go or no-go decision maker named.
- [ ] Estimand, population, assignment unit, arms, metric, MDE, power, duration, and analysis pre-registered.
- [ ] Budget and pacing contamination controls approved.
- [ ] Assignment, exposure, and sample-ratio checks implemented.
- [ ] Multiple-variant selection-bias control approved.
- [ ] Advertiser, fill, participation, concentration, and user harm margins approved.
- [ ] Actual billed-revenue semantics reviewed by finance.
- [ ] Sequential stopping and emergency stop rules approved.
- [ ] Ranking or write kill switch tested under queued and in-flight work.
- [ ] Rollback drill passed.
- [ ] Security, privacy, legal, Ads engineering, Ads science, experimentation, SRE, and finance sign off.

## 7. Risk register

Every risk requires a named owner and review date before the phase that can trigger it.

| ID | Risk | Trigger | Impact | Primary control | Owner | Status |
|---|---|---|---|---|---|---|
| R01 | Uncontrolled creative drift | Output changes locked attributes | Invalid experiment or brand issue | One-axis contract plus visual and human checks | TBD | Open |
| R02 | Noisy winner or winner's curse | Best observed variant selected from many | False learning and wasted follow-up | Independent confirmation or approved multiple-comparison method | Experimentation, TBD | Open |
| R03 | Signal miscalibration | Predicted CTR diverges from true response | Wrong sensitivity or ranking effect | Calibration monitoring and separate observed field | Ads ML, TBD | Open |
| R04 | Auction-model misspecification | Production mechanism differs from scenario | Reversed economics conclusion | Model card, internal review, sensitivity, claim ceiling | Ads science, TBD | Open |
| R05 | Learner disagreement | Hedge and EXP3-IX reverse ordering | Cherry-picked revenue story | Report together and trigger `IS7_ASSUMPTION_SIGN_CONFLICT` | Ads science, TBD | Open |
| R06 | Bidder adaptation | Long-run behavior differs from fixed-bid result | Short-run lift does not persist | Fixed and adaptive estimates, staged experiment | Ads science, TBD | Open |
| R07 | Budget or pacing interference | Treatment changes spend opportunity | Contaminated causal estimate | Arm isolation and pacing review | Ads engineering, TBD | Open |
| R08 | Creative fatigue | Early response decays with exposure | Misleading short test | Exposure and time analysis | Experimentation, TBD | Open |
| R09 | Cross-context leakage | Same user or campaign crosses arms | Biased estimate | Assignment-unit design and contamination checks | Experimentation, TBD | Open |
| R10 | Cross-tenant leakage | Asset or outcome joins another tenant | Confidentiality incident | Repository authorization and composite tenant keys | Security, TBD | Open |
| R11 | Unauthorized training use | Private assets enter shared training | Contract and privacy breach | Explicit training-use policy and opt-in | Privacy and legal, TBD | Open |
| R12 | Rights or likeness dispute | Input or output uses protected content | Legal and reputational harm | Provenance, approval, support, takedown | Legal, TBD | Open |
| R13 | Prompt injection or malicious upload | External content influences tools or parser | Code, data, or policy compromise | Treat as data, schemas, egress and media controls | Security, TBD | Open |
| R14 | Forged outcomes or attribution fraud | Source event replay or spoofing | Optimizer reward gaming | Signed source and idempotent joins | Data security, TBD | Open |
| R15 | API version or alias drift | Provider changes model behavior | Reproducibility and quality regression | Dated aliases, model discovery, claim expiry | Imagine owner, TBD | Open |
| R16 | Cost runaway | Retry loop or unlimited variants | Financial loss | Hard caps, unknown-cost hold, kill switch | SRE and finance, TBD | Open |
| R17 | Provider lock-in or outage | Imagine unavailable or contract changes | Workflow interruption | Small port, replay, hold behavior | Engineering, TBD | Open |
| R18 | Outcome delay or missingness | Incomplete conversion window | Premature decision | Freshness gate and `HOLD` | Data, TBD | Open |
| R19 | Advertiser exclusion | Revenue gain concentrates allocation | Market and advertiser harm | Participation and concentration countermetrics | Ads economics, TBD | Open |
| R20 | User-experience harm | More clicks accompany negative feedback | Platform harm | User countermetrics and stop boundaries | Product integrity, TBD | Open |
| R21 | Misleading revenue communication | Simulation called causal revenue | Decision and reputational harm | Claim register and finance approval | Product and finance, TBD | Open |
| R22 | Rollback failure | Queued retries bypass disable | Continued harm | Dual-point kill switch and drill | SRE, TBD | Open |
| R23 | Operator overload | Too many holds and reviews | Slow workflow and unsafe overrides | Queue SLO, reason analytics, capacity | Operations, TBD | Open |
| R24 | Sparse-cohort reidentification | Fine contexts reveal individuals | Privacy harm | Minimum cohorts and suppression | Privacy, TBD | Open |

## 8. Open decisions

### Product

1. Is the first reviewed product offline demo, internal shadow, or draft-only beta?
2. Who is the production product DRI and final decision maker?
3. Which advertiser persona and one mutation axis define the first demo?
4. What is the primary generation-efficiency metric and same-budget baseline?
5. Is ImagineSignal the working name only, or approved for product use?

### Imagine and infrastructure

6. Does this account's SuperGrok usage pool include public developer API calls, and what does the Console show?
7. Which dated model is pinned for the benchmark?
8. When is quality upgrade justified?
9. Will the prototype store local digested bytes or provider file IDs?
10. What are asset retention, deletion, residency, and watermark requirements?

### Outcomes and experiments

11. What is the first response metric, assignment unit, attribution window, MDE, and maximum duration?
12. Which aggregate data source is approved?
13. What minimum cohort and freshness thresholds apply?
14. How are repeated exposures, creative fatigue, multiple variants, and delayed conversions handled?
15. Which harm margins block advancement?

### Ads economics

16. What exact scoring, pricing, billing, pacing, and targeting behavior is in scope?
17. Is predicted CTR available, and how is it calibrated?
18. Is billed revenue available, or only advertiser spend and attributed value?
19. What internal state is available for counterfactual support?
20. Is soft-floor experimentation explicitly out of scope? The recommendation is yes.

### Governance and launch

21. Can private outcomes inform any shared model?
22. What human approval is required for a draft, publish, or ranking action?
23. Who owns every kill switch, on-call, incident command, support, and deletion process?
24. Which claims may appear in a demo, blog, sales deck, API documentation, or press material?

## 9. Reviewer matrix

| Reviewer | Required scope | Name | Decision | Conditions and expiration |
|---|---|---|---|---|
| Product decision maker | Product value, scope, launch tier, business risk | TBD | Pending | |
| Product DRI | PRD, workflow, non-goals, metrics | Arun Sharma for prototype; production TBD | Pending | |
| Engineering lead | Architecture, contracts, implementation, rollback | TBD | Pending | |
| Imagine API owner | Model, endpoint, moderation, cost, fallback | TBD | Pending | |
| Ads auction engineering | Scoring, pricing, pacing, candidate and write correctness | TBD | Pending | |
| Ads science or economist | Mechanism assumptions, learners, welfare | TBD | Pending | |
| Experimentation lead | Estimand, randomization, power, analysis, stop rules | TBD | Pending | |
| Data engineering | Outcome quality, lineage, attribution, replay | TBD | Pending | |
| SRE | SLOs, capacity, monitoring, on-call, rollback drill | TBD | Pending | |
| Security | Threat model, credentials, isolation, abuse | TBD | Pending | |
| Privacy | Data minimization, retention, deletion, user events | TBD | Pending | |
| Data governance | Classification, permitted use, access, training | TBD | Pending | |
| Legal and compliance | Terms, intellectual property, likeness, regional requirements | TBD | Pending | |
| Advertiser integrity | Provider and ads-policy controls as guardrails | TBD | Pending | |
| Finance or revenue analytics | Revenue semantics, reconciliation, cost | TBD | Pending | |
| Advertiser experience | Workflow, override, support, communication | TBD | Pending | |
| Incident commander | Incident and rollback readiness | TBD | Pending | |

A write-enabled or ranking-enabled launch requires affirmative sign-off from product, engineering, Ads auction engineering, Ads science, experimentation, security, privacy, SRE, and finance. Any unresolved P0 blocker is `NO_GO`.

## 10. Review response template

```text
Reviewer:
Role:
Document version:
Requested phase:
Decision: PASS / CONDITIONAL / FAIL

Strongest supported claim:

Most important unsupported assumption:

P0 blocker, if any:

Required change and acceptance evidence:

Named owner:

Deadline:

Automatic fallback if unresolved:

Residual risk accepted:

Re-review trigger or expiration:
```

