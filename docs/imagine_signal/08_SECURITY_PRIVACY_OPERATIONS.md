# ImagineSignal security, privacy, and operations plan

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed; required controls are not yet implemented |
| Author | Arun Sharma |
| Date | 2026-08-05 |
| Current operating mode | Local frozen replay only |
| Production on-call | TBD |
| Security and privacy approvers | TBD |

## 1. Current operational judgment

ImagineSignal is not ready for production credentials, customer assets, outcome feeds, ad publishing, spend changes, or ranking influence. The design supports local replay now and defines the gates for later stages.

The first implementation should be structurally incapable of a production write. A feature flag alone is not sufficient if a write client or credential is present in the process.

## 2. Security objectives

1. Prevent cross-tenant asset, prompt, outcome, receipt, and campaign access.
2. Prevent model or simulator output from directly publishing, spending, or changing ranking.
3. Keep credentials and signed URLs out of prompts, hashes, logs, fixtures, and receipts.
4. Verify every input, output, media object, event, approval, and external response before admission.
5. Bound cost, concurrency, retries, storage, and queue growth.
6. Preserve an immutable audit line for every consequential decision.
7. Make generation, ingestion, recommendation, approval, ranking export, and publishing independently disableable.

## 3. Threat model

| Threat | Example path | Preventive controls | Detection and response | Release condition |
|---|---|---|---|---|
| Cross-tenant read or write | Child asset references another tenant's parent | Tenant field on every object, repository-level authorization, composite tenant keys | Security alert, quarantine, access audit | Zero known paths; isolation tests pass |
| API credential theft | Key appears in fixture or trace | Managed secrets, transport-only injection, redaction, no credential fields in contracts | Secret scanning, key rotation, incident review | No secret in repository or artifact |
| Response-secret leakage | Provider returns confidential metadata that is recorded | Response allowlist plus recursive secret scan before fixture write | Fixture scan blocks commit and rotates affected secret | Implement before live recording |
| Prompt or content injection | Uploaded product page attempts to change system behavior | Treat external text as data, fixed schemas, no tool authority in compiler | Gate failure and suspicious-input trace | Adversarial test suite passes |
| Malicious media | Crafted image exploits parser | Content-type and magic-byte checks, size and dimension limits, isolated decoder, malware scan in production | Quarantine and security alert | Approved media pipeline before customer uploads |
| SSRF | Source image URL targets an internal service | Allowlisted scheme and host, DNS and redirect controls, size and timeout limits, prefer base64 or file ID | Blocked-fetch metrics and alert | No unrestricted server-side fetch |
| Signed-URL leakage | Temporary asset URL appears in logs or receipt | URL redaction, short handling lifetime, durable digest identity | Log scan and URL revocation | URL absent from general logs and fixtures |
| Forged or replayed outcomes | Attacker inflates clicks or value | Signed source, nonce or source ID, idempotency, tenant and experiment joins | Duplicate and signature counters, quarantine | Source authentication and replay tests pass |
| Approval bypass | Model invokes publish adapter directly | Separate enforcement service, no model credentials, dual authorization for consequential writes | Unauthorized-write alert, kill switch, incident | No direct model-to-write path |
| Cost exhaustion | Recursive edits or retries produce many paid calls | Per-request, family, tenant, day, model-tier, and dollar caps; bounded retries | Cost-rate alerts and generation kill switch | Cap and ambiguous-retry tests pass |
| Reward gaming | Optimizer exploits incomplete or delayed metrics | Frozen definitions, multiple guardrails, delayed conversion handling, hold state | Drift and anomaly dashboards, human review | Experimentation approval |
| Audit deletion | Operator or service changes a past receipt | Append-only ledger, restricted writes, immutable backups | Integrity scan and missing-receipt alert | Production write blocked until ledger proven |
| Commercial inference | Sparse data reveals competitor bids or willingness to pay | Restricted access domain, aggregation, minimum cohorts, no external inferred values | Access logs and sparse-cell suppression | Ads science, legal, and privacy approval |
| Supply-chain compromise | Dependency or image injects code | Pinned dependencies, advisory scan, build provenance, non-root image | CI scan and incident response | Lock or constraints file before deployment |
| Operator abuse | Privileged user exports another tenant's data | Least privilege, approval, break-glass logs, periodic access review | Audit anomaly and security review | Named access owner and review schedule |

Any cross-tenant exposure, unauthorized publish, unauthorized spend, unauthorized ranking change, production secret in a fixture, or missing audit trace for a production write is a zero-tolerance event.

## 4. Existing repository risks to resolve before production reuse

Repository inspection found useful patterns and several limits that must be explicit:

1. `FixtureStore` rejects secret-shaped request fields and values, but it does not apply the same recursive secret check to provider responses before recording. ImagineSignal must scan or allowlist both sides.
2. The current cost parser can turn a missing or invalid numeric cost field into zero. ImagineSignal must distinguish actual zero, unavailable cost, and invalid cost. Unknown cost is not free and blocks a paid next action.
3. The current G5 budget helper is not part of `run_verdict_gates`. ImagineSignal must run budget checks immediately before and after every potentially billable operation.
4. The current in-process review queue is volatile and is not a production data store.
5. The current fixture store is JSON and filesystem based; large image and video bodies need a digest-linked blob store.
6. The current compiler cache is process-local and not tenant scoped.
7. Current media contracts favor local paths; production needs private object handles or provider file IDs plus verified content hashes.
8. A valid image bounding box proves geometry, not that the named visual object is semantically present. Deterministic provenance and model-based visual judgment must remain separate claims.

These are not reasons to discard the repository. They define the correct reuse boundary.

## 4a. Provider data-retention finding (verified 2026-08-05)

Two authorized smoke probes against `POST https://api.x.ai/v1/images/generations` returned:

| Response header | Value |
|---|---|
| `x-zero-data-retention` | `false` |
| `x-data-retention` | `general` |

xAI retains request data under general retention for this account and endpoint. Only synthetic or non-sensitive prompts and assets may be sent. Do not send real brand briefs, customer creative, personal data, or other confidential content through this API until a separate retention and training-use review says otherwise. Source: `hackathon/COST_LEDGER.md` section 1.

## 5. Privacy impact assessment

### Planned data

| Data | Classification | MVP use | Production decision needed |
|---|---|---|---|
| Synthetic campaign brief | Public or internal demo | Yes | Provenance only |
| Real brand brief, prompt, or kit | Confidential | No | Purpose, access, training use, retention, deletion |
| Base and generated media | Confidential by default | Synthetic demo only | Rights, likeness, residency, retention, deletion |
| Aggregate creative outcomes | Restricted | Synthetic or frozen only | Source authorization, minimum cohort, attribution, retention |
| User-level exposure or event | Highly restricted | No | Avoid in optimizer; separate review if ever required |
| Auction bids, scores, prices, logs | Highly restricted | No | Separate access domain and economics review |
| API keys and OAuth tokens | Secret | No stored value | Managed secret system and rotation |
| Decision receipts | Confidential | Synthetic only | Tenant access, retention, legal hold, export, deletion |

### Privacy defaults

- Aggregate at campaign, creative, context, and experiment-window level.
- Keep raw user events out of the creative optimizer.
- Apply approved minimum cohort sizes and suppress sparse cells.
- Do not infer sensitive user categories for creative optimization.
- Do not use one advertiser's private assets or outcomes to optimize another advertiser without explicit authorization and legal basis.
- Do not train a shared model on advertiser assets or outcomes without explicit opt-in.
- Keep inferred bidder values internal, restricted, and labeled as model-implied.
- Preserve provenance and permitted-use metadata for every source and generated asset.
- Support tenant export and deletion before an advertiser beta.
- Keep public X content, advertiser-confidential data, restricted outcomes, and auction data in separate classifications and access paths.

### Questions that block restricted data

1. What is the minimum data necessary for the primary metric?
2. What contractual and legal purpose permits each field?
3. Are faces, voices, copyrighted assets, or personal likenesses included?
4. Does xAI or another provider retain or train on the selected API inputs and outputs under the applicable account terms?
5. Which regions process and store the data?
6. What are online, backup, fixture, ledger, and provider-retention periods?
7. How does a tenant export or delete briefs, assets, outcomes, and receipts?
8. How are legal hold, consent withdrawal, rights disputes, and data-subject requests handled?

## 6. Data governance

Before shadow mode, create and approve:

- Data inventory and flow map.
- Owner and permitted-use matrix.
- Data-classification policy.
- Prompt, asset, outcome, auction, log, and receipt retention schedules.
- Deletion behavior for online data, backups, provider files, and public URLs.
- Regional-processing map.
- Training-use and cross-tenant-use policy.
- Dataset and experiment cards.
- Lineage and provenance standard.
- Access-review and break-glass procedure.
- Third-party processor list.
- Data-quality checks and sparse-cohort rules.
- Inferred-data classification.

Undefined retention, training use, tenant deletion, auction-data ownership, purpose limitation, or sparse-cohort handling blocks the relevant launch stage.

## 7. SLO and SLI plan

Every production SLO requires an SLI, data source, target, window, error budget, alert, owner, degradation behavior, and rollback trigger. Targets marked `TBD` are launch blockers, not placeholders that can be ignored.

| SLI | Definition | Offline target | Shadow or production target |
|---|---|---:|---|
| Deterministic replay consistency | Same committed inputs produce the same admitted decision and receipt hash under the pinned version | 100 percent | 100 percent for pinned replay |
| Lineage completeness | Admitted assets with all required parent, root, tenant, request, media, model, cost, and trace fields | 100 percent | 100 percent |
| Receipt completeness | Terminal decisions with an immutable receipt | 100 percent | 100 percent |
| Unknown-cost admission | Paid operations admitted while cost is unknown or invalid | 0 | 0 |
| Unauthorized writes | Publish, spend, ranking, or campaign writes without current authorization | 0 | 0 |
| Cross-tenant events | Confirmed cross-tenant reads or writes | 0 | 0 |
| Secrets in fixtures | Committed credentials or signed secrets | 0 | 0 |
| Decision availability | Successful eligible decision requests divided by eligible requests | Measure locally | TBD |
| Added decision latency | P50, P95, and P99 post-processing latency, with and without generation | Benchmark first | TBD |
| Outcome join completeness | Eligible aggregate records joined to exact creative and experiment | Benchmark first | TBD |
| Outcome freshness | Delay between measurement end and admitted snapshot | Benchmark first | TBD |
| Duplicate suppression | Exact or approved near duplicates stopped before paid escalation | Benchmark first | TBD |
| Cost reconciliation | Paid calls with provider-reported or independently reconciled cost | 100 percent in recorded set | TBD, proposed 100 percent |
| Approval enforcement | Consequential actions with valid current approval | Not applicable | 100 percent |
| Experiment contamination | Exposures assigned to the wrong arm | Not applicable | 0 within approved detection tolerance |
| Review queue age | Age distribution for `HOLD` and `REVIEW` | Measure | TBD |
| Kill-switch time | Decision-to-confirmed-disable time by surface | Drill locally when surface exists | TBD |
| Tenant deletion completion | Time to remove data from each approved storage tier | Not applicable | TBD |

## 8. Capacity and cost plan

### Capacity dimensions

- Peak and sustained generation requests.
- Maximum outputs per request.
- Standard and quality model mix.
- Input reference count and size.
- Asset and video storage growth.
- Outcome ingestion rate and lateness.
- Audit-ledger and trace growth.
- Retry amplification after provider failures.
- Review queue saturation.
- Provider and X Ads rate limits.

### Cost formula

For a family:

```text
generation_cost = sum(provider_reported_cost_in_usd_ticks) / 10,000,000,000
storage_cost = stored_GiB * days * current_storage_rate
download_cost = downloaded_GiB * current_download_rate
family_cost = generation_cost + storage_cost + download_cost + internal_compute_cost
```

Do not compute an unknown provider cost as zero.

At the price snapshot in the integration note, four standard one-reference edits cost approximately `4 * $0.022 = $0.088`. Upgrading one finalist to a quality 1K one-reference edit adds approximately `$0.06`, for an illustrative provider total of `$0.148`. This is arithmetic from the 2026-08-05 public price page, not a measured run or future price guarantee.

### Cost controls

- Per-call maximum outputs.
- Per-family standard and quality image counts.
- Per-tenant and per-day dollar ceilings.
- Postpaid disabled by default for local work.
- Auto top-up disabled unless explicitly approved.
- Bounded retries with ambiguous-success reconciliation.
- Duplicate and integrity checks before quality or video.
- Stop generation when blob persistence, ledger, or cost telemetry is unhealthy.
- Alert on cost rate, not only cumulative cost.

The system degrades to `KEEP`, `HOLD`, `REVIEW`, or `STOP`, never an unbounded generation loop.

## 9. Observability

### Trace identity

One trace connects:

```text
campaign brief
-> family plan
-> Imagine request
-> generated bytes and asset hash
-> parent lineage
-> mutation declaration
-> admission gates
-> experiment assignment
-> outcome snapshot
-> signal estimate
-> auction scenario
-> decision
-> human review
-> next action
```

### Structured log rules

- Stable trace, tenant, campaign, family, creative, experiment, and receipt IDs in protected fields.
- Stable gate and adapter error codes.
- No credentials, authorization headers, raw private prompts, signed URLs, or raw user-level outcomes.
- No full image bytes or base64 in logs.
- Provider request IDs, resolved model, latency, retry count, and cost ticks.
- Audit events are never sampled away.
- Retention follows data classification.

### Required dashboards

1. Generation: requests, outputs, failures, latency, cost, model tier, retries, rate limits, and duplicates.
2. Admission: pass and fail counts, gate codes, action coercions, holds, reviews, stops, and overrides.
3. Lineage: orphan assets, cycles, hash mismatch, missing parent, locked-attribute drift, and cross-tenant attempts.
4. Outcomes: volume, join failures, duplicates, staleness, attribution mismatch, and delayed conversion.
5. Experiments: assignment balance, exposure mismatch, sample-ratio mismatch, arm contamination, budget imbalance, and stopping status.
6. Business and welfare: qualified-creative yield, cost per qualified creative, response, advertiser outcomes, fill, participation, concentration, and user guardrails.
7. Security and privacy: authorization failures, secret detections, unusual access, sparse-cell suppressions, exports, and deletion jobs.

## 10. Deployment modes and rollout

### Phase 0: local frozen replay

- No credentials.
- Network blocked.
- Synthetic or committed non-sensitive data only.
- No external writes.
- Results visibly labeled `FROZEN_REPLAY` or `SIMULATED`.

### Phase 1: bounded Imagine recording

- Scoped development key.
- Non-sensitive demo assets.
- Hard call and dollar caps.
- Postpaid disabled or explicitly capped.
- Replay rerun after key removal.

### Phase 2: internal read-only shadow

- Named owners and on-call.
- Approved aggregate data source.
- Tenant isolation and data governance.
- Recommendations logged only.
- No publishing, spend, ranking, or targeting changes.

### Phase 3: internal draft-only dogfood

- Authorized internal users.
- Human approval.
- Draft adapter only.
- Tenant and campaign quotas.
- Export and deletion active.

### Phase 4: invited advertiser draft beta

- Security, privacy, legal, support, and operations sign-off.
- Draft payload or export only.
- No autonomous campaign action.
- Rights and provenance support path.

### Phase 5: display-only randomized experiment

- Creative randomized after allocation.
- Existing rank score and auction price frozen.
- Causal response measured on already-won impressions.

### Phase 6: signal-aware limited experiment

- Separate authorization.
- Tiny traffic slice.
- Budget and pacing isolation.
- Immediate ranking-signal kill switch.
- No floor or reserve changes.

### Phase 7: controlled expansion

Requires SLO compliance, causal evidence, healthy countermetrics, no unresolved P0 risk, trained support and on-call, deletion proof, rollback drill, current claim register, and fresh sign-offs.

## 11. Kill switches

Implement before the corresponding surface exists:

- All Imagine generation.
- Quality model calls.
- Video calls.
- Outcome ingestion.
- Optimization and next-action recommendations.
- Human-approved draft creation.
- Campaign publishing.
- Ranking-signal export.
- One tenant.
- One campaign.
- One context or query family.
- One provider model or version.

Flags apply at both request admission and worker execution so queued work cannot bypass a later disable.

## 12. Rollback triggers and proof

Rollback triggers include:

- Unauthorized write or approval bypass.
- Cross-tenant access.
- Missing or mutable audit record.
- Assignment contamination or sample-ratio failure.
- Cost runaway or provider instability.
- Outcome join or freshness collapse.
- Signal calibration drift.
- Revenue, advertiser, participation, fill, concentration, or user harm boundary crossed.
- Data-retention or deletion failure.
- Gate bypass.
- Incident commander decision.

Before any write-enabled launch, demonstrate that:

1. The relevant kill switch disables both new and queued work.
2. In-flight retries cannot re-enable or duplicate the action.
3. Existing campaigns remain valid.
4. Budget and pacing ownership returns to the prior system.
5. Audit evidence remains queryable.
6. The previous model, control creative, or no-signal behavior is restored.
7. Experiment assignments stop.
8. Operators receive confirmation.
9. Required customer communication is triggered.
10. Monitoring continues through a predeclared washout period.

A written rollback plan without a completed drill is a launch blocker.

## 13. Incident and support plan

| Incident class | Immediate containment | Required escalation |
|---|---|---|
| Unauthorized publish, spend, or ranking change | Disable write surface, preserve trace, halt queued work | Incident commander, Ads engineering, security, product, finance |
| Cross-tenant exposure | Disable affected tenant and data path, revoke credentials | Security, privacy, legal, incident commander |
| Incorrect revenue or outcome report | Withdraw claim and dashboard, freeze receipts | Data, experimentation, finance, product |
| Experiment contamination | Stop assignment, preserve arm and exposure logs | Experimentation, Ads engineering, product |
| Data deletion failure | Stop new retention-expanding work, preserve request audit | Privacy, data governance, legal |
| Rights or likeness complaint | Disable public URL or draft, preserve provenance | Legal, advertiser integrity, support |
| API cost runaway | Disable generation and top-up, reconcile ambiguous calls | SRE, finance, Imagine owner |
| Provider outage or regression | Switch to hold or replay, stop paid retries | SRE, Imagine owner, product |
| Outcome-source outage | Freeze decisions at `HOLD` | Data owner, SRE, experimentation |
| Approval bypass | Disable draft or write adapter, revoke actor token | Security, product, incident commander |

For each class, the production runbook must name severity, detection, first responder, incident commander, containment, customer notification, privacy and legal escalation, rollback, evidence preservation, recovery, and postmortem requirement.

Customer and operator support material must explain each action, why an asset was held, how to override within authorization, how to delete data, how to report rights issues, how attribution works, and what revenue language does and does not mean.

## 14. Production readiness checklist

- [ ] Named product, engineering, SRE, security, privacy, data, finance, and incident owners.
- [ ] Approved scope and launch tier.
- [ ] Tenant authorization and isolation tests.
- [ ] Request and response secret scanning.
- [ ] Media upload and URL-fetch hardening.
- [ ] Immutable receipt ledger.
- [ ] Provider and Ads credentials scoped and rotated.
- [ ] Cost caps and unknown-cost fail-closed behavior.
- [ ] Approved data inventory, retention, deletion, training-use, and cross-tenant policies.
- [ ] SLO targets and alerts approved.
- [ ] Capacity and cost model reviewed.
- [ ] Dashboards and on-call runbooks exercised.
- [ ] Feature flags and kill switches tested.
- [ ] Rollback drill passed.
- [ ] Support and incident plans staffed.
- [ ] Experiment and claim registers approved.
- [ ] No unresolved P0 blocker.

