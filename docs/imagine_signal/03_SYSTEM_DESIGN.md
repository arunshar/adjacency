# ImagineSignal system design

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed |
| Author | Arun Sharma |
| Reviewers | Product, Imagine API, Ads engineering, data, experimentation, security, privacy, SRE |
| Last reviewed | 2026-08-05 |
| Re-review trigger | Any production-data access, write path, ranking influence, or provider-contract change |

## 1. Design goals

1. Generate small creative families where one declared attribute changes at a time.
2. Preserve a complete, immutable line from campaign brief to output, outcome, simulation, decision, and human override.
3. Reduce wasted generation through duplicate checks, evidence-aware stopping, and staged quality upgrades.
4. Separate observed response, predicted response, simulated economics, and causal production evidence.
5. Make every next action deterministic after the proposal and evidence stages.
6. Reuse the existing repository's contract, gate, replay, and review patterns without changing brand-safety semantics.
7. Keep every production write, spend change, and ranking change outside the MVP boundary.

## 2. Context diagram

```mermaid
flowchart LR
    U["Creative strategist or operator"] --> IS["ImagineSignal"]
    IS --> XI["xAI Grok Imagine API"]
    XI --> IS
    IS --> AS["Creative asset storage"]
    IS --> EX["Approved experiment and aggregate outcomes"]
    EX --> IS
    IS --> ADJ["Existing Adjacency placement compatibility"]
    ADJ --> IS
    IS --> RV["Human review"]
    IS --> RC["Decision receipt and dashboard"]
    IS -. "future, disabled" .-> XADS["X Ads draft or ranking adapters"]
```

The X Ads connection is a future boundary. It is present in the diagram so reviewers can inspect the eventual trust boundary, but its write path is absent from the MVP implementation.

## 3. Container design

```mermaid
flowchart TB
    subgraph Client["Operator boundary"]
        UI["Local review UI or internal console"]
        CLI["CLI and test harness"]
    end

    subgraph Service["ImagineSignal service boundary"]
        API["API and authorization"]
        BRIEF["Brief and brand compiler"]
        PLAN["Controlled mutation planner"]
        ORCH["Family orchestrator"]
        DIFF["Integrity and duplicate checks"]
        SIGNAL["Aggregate outcome estimator"]
        AUCTION["Auction Sensitivity Layer"]
        GATES["Deterministic IS0-IS8 gates"]
        RECEIPT["Receipt builder"]
        APPROVAL["Human approval adapter"]
        FLAGS["Feature flags, quotas, and kill switches"]
    end

    subgraph Data["Tenant-scoped data boundary"]
        META["Metadata and lineage store"]
        BLOBS["Content-addressed asset store"]
        LEDGER["Append-only decision ledger"]
        FIX["Offline fixture and replay store"]
        METRICS["Metrics and traces"]
    end

    subgraph External["External provider and ads boundaries"]
        IMAGINE["Grok Imagine API"]
        OUTCOMES["Approved aggregate outcome source"]
        EXPERIMENT["Approved assignment service"]
        ADS["X Ads draft or ranking adapters, future"]
    end

    UI --> API
    CLI --> API
    API --> FLAGS
    API --> BRIEF
    BRIEF --> PLAN
    PLAN --> ORCH
    ORCH --> FIX
    ORCH --> IMAGINE
    ORCH --> BLOBS
    ORCH --> DIFF
    DIFF --> GATES
    OUTCOMES --> SIGNAL
    EXPERIMENT --> SIGNAL
    SIGNAL --> AUCTION
    AUCTION --> GATES
    GATES --> RECEIPT
    GATES --> APPROVAL
    RECEIPT --> LEDGER
    BRIEF --> META
    PLAN --> META
    SIGNAL --> META
    ORCH --> METRICS
    GATES --> METRICS
    APPROVAL -. "future authorized draft only" .-> ADS
```

## 4. Component responsibilities

| Component | Owns | Must not own |
|---|---|---|
| API and authorization | Tenant identity, idempotency, schema version, request tracing | Creative judgment or auction logic |
| Brief and brand compiler | Structured objective, contexts, mutable axis, locked constraints | Provider calls or ad publishing |
| Mutation planner | Parent, axis, levels, prompt fragments, expected family size | Outcome selection after seeing results |
| Family orchestrator | Budgeted generation or replay, retries, state transitions | Final recommendation |
| Imagine adapter | Provider request mapping, response normalization, cost and moderation metadata | Business gates or credential storage |
| Asset store | Verified bytes, digest, media metadata, retention state | Provider URLs as durable identity |
| Integrity and duplicate checks | Hash integrity, parent existence, exact duplicate and replaceable near-duplicate checks | Aesthetic ranking |
| Outcome estimator | Aggregate counts, uncertainty, attribution window, data freshness | Raw user-level optimization or auction claims |
| Auction Sensitivity Layer | Scenario-specific score and economics simulation | Live bidding, floors, reserves, or production claims |
| Gate engine | Evidence-to-action ceiling and stable reason codes | Network, clock, or free-form model decisions |
| Approval adapter | Authorized human action and reason | Silent promotion or policy bypass |
| Receipt builder | Complete immutable explanation and evidence references | Mutating source evidence |
| Flags, quotas, and kill switches | Tenant, campaign, action, model, and environment controls | Hiding a failed gate |

## 5. Core synchronous flow

```mermaid
sequenceDiagram
    actor Operator
    participant API as ImagineSignal API
    participant Planner as Mutation Planner
    participant Imagine as Recorded Imagine Adapter
    participant Store as Asset and Lineage Stores
    participant Gates as Deterministic Gates
    participant Ledger as Receipt Ledger

    Operator->>API: Submit versioned brief and idempotency key
    API->>Planner: Compile one-axis family
    Planner-->>API: Family plan and request hashes
    API->>Gates: IS0 request and budget admission
    alt Replay mode
        API->>Imagine: Resolve committed fixtures
    else Explicit record mode
        API->>Imagine: Bounded provider calls
    end
    Imagine-->>API: Normalized metadata and verified output bytes
    API->>Store: Persist lineage and content digests
    API->>Gates: IS1 through IS4 asset admission
    Gates-->>API: TEST, HOLD, REVIEW, or STOP ceiling
    API->>Ledger: Append receipt
    API-->>Operator: Family, cost, gate chain, and allowed next step
```

This flow does not publish or assign traffic.

## 6. Outcome and sensitivity flow

```mermaid
sequenceDiagram
    participant Source as Approved aggregate outcome source
    participant API as Outcome API
    participant Signal as Signal Estimator
    participant Auction as Auction Sensitivity Layer
    participant Gates as IS Gate Engine
    participant Review as Human Review
    participant Ledger as Receipt Ledger

    Source->>API: Signed, idempotent aggregate snapshot
    API->>Signal: Validate join, window, freshness, and origin
    Signal-->>API: Observed estimate and uncertainty
    API->>Auction: Paired baseline and variant scenario
    Auction-->>API: Boundary and economic sensitivity by assumption
    API->>Gates: IS5 through IS8 evidence admission
    alt Insufficient or conflicting evidence
        Gates->>Review: HOLD or REVIEW with stable codes
    else Evidence permits another test
        Gates-->>API: TEST recommendation
    end
    API->>Ledger: Append new receipt version
```

Only an authorized later experiment can lift the action ceiling beyond `TEST`.

## 7. Trust boundaries

### Advertiser tenant boundary

Every brief, asset, outcome, scenario, and receipt carries `tenant_id`. Parent-child links and joins must match the tenant. Cross-tenant reads, writes, or learned private outcomes are release blockers.

### xAI provider boundary

The adapter sends only the approved prompt and media. Credentials are injected at the transport and never enter hashes, fixtures, logs, or receipts. Responses remain untrusted until the schema, moderation status, bytes, digest, and cost fields are validated.

### Asset URL boundary

Public or signed URLs are not fetched without scheme, host, redirect, size, content-type, and timeout controls. The preferred prototype path is base64 output decoded locally or a private provider `file_id`. A temporary URL is never treated as durable storage.

### Outcome boundary

The planned optimizer consumes aggregate snapshots, not raw user events. Each snapshot identifies its source, experiment arm, campaign, creative, context, attribution method, window, freshness, and digest.

### Auction-log boundary

Candidate bids, competitor scores, prices, and billed revenue are highly restricted. They are absent from the public prototype. Any later access needs a separate owner, purpose limitation, access domain, retention decision, and audit.

### Human approval and production-write boundary

No model output or simulation reaches a write adapter directly. An approved gate result, current campaign version, feature flag, authorization state, and idempotency key must converge at a separate enforcement point. That point is not implemented in the MVP.

### Offline evaluation boundary

Replay mode has no production credentials and no production-write client. The process must be incapable of switching to live because of a missing fixture or provider error.

## 8. Data stores

| Store | Data | Consistency | Retention |
|---|---|---|---|
| Metadata and lineage | Versioned briefs, mutations, assets, outcomes, scenarios, approvals | Transactional for parent and child writes | Policy TBD before live data |
| Content-addressed blobs | Source and generated media keyed by SHA-256 | Write once, digest verified | Policy TBD; synthetic fixtures may be committed |
| Decision ledger | Append-only receipts and overrides | Immutable append; every terminal decision required | Longer than mutable state, policy TBD |
| Fixture store | Canonical request, normalized response metadata, asset digest | Content-addressed and secret scanned | Committed only for non-sensitive assets |
| Metrics and traces | Operational counters and structured traces | At-least-once with deduplication | Classification-specific, no raw secrets or events |

For the local prototype, files can implement these interfaces. A production deployment may use a relational metadata store, object storage, an append-only audit stream, and a metrics platform. The contracts must remain storage-independent.

## 9. State machine

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> PLANNED: brief admitted
    PLANNED --> GENERATING: budget admitted
    GENERATING --> GENERATED: verified outputs stored
    GENERATING --> HOLD: ambiguous provider result
    GENERATED --> TEST_CANDIDATE: lineage and asset gates pass
    GENERATED --> REVIEW: constraint or moderation ambiguity
    GENERATED --> STOPPED: terminal failure or budget stop
    TEST_CANDIDATE --> TESTING: authorized assignment outside MVP
    TESTING --> OUTCOME_READY: complete aggregate window
    TESTING --> HOLD: incomplete or stale outcomes
    OUTCOME_READY --> EVALUATED: signal and sensitivity complete
    EVALUATED --> TEST_CANDIDATE: another bounded test justified
    EVALUATED --> REVIEW: assumption conflict or guardrail issue
    EVALUATED --> STOPPED: no justified next step
    EVALUATED --> KEEP_CONTROL: control remains preferred
    REVIEW --> TEST_CANDIDATE: authorized resolution
    REVIEW --> KEEP_CONTROL: authorized resolution
    REVIEW --> STOPPED: authorized resolution
```

`PROMOTED` is intentionally absent from the MVP state machine.

## 10. Deployment modes

| Mode | Network | Data | Allowed actions | Maximum evidence class |
|---|---|---|---|---|
| `fixture` | None | Synthetic and committed replay | Generate by replay, evaluate, explain | `FROZEN_REPLAY` or `SIMULATED` |
| `record` | xAI Imagine only | Non-sensitive demo data | Record bounded outputs, then replay | `IMPLEMENTED` until benchmarked |
| `shadow` | Approved read paths only | Aggregate permitted-use outcomes | Recommend and log, no writes | `SHADOW_ESTIMATE` |
| `draft_beta` | Approved draft adapter | Tenant data with human approval | Create draft only | Evidence-specific |
| `experiment_display_only` | Authorized experiment | Live aggregate outcomes | Randomize creative after allocation | `RANDOMIZED_DISPLAY_ONLY` |
| `experiment_signal_aware` | Authorized ranking experiment | Restricted auction and outcome data | Bounded signal test with kill switch | `RANDOMIZED_END_TO_END` |

Mode is explicit configuration, not inferred from credentials. A lower mode cannot call a higher-mode adapter.

## 11. Failure behavior

| Failure | Response | Retry | Decision ceiling |
|---|---|---|---|
| Missing fixture | Fail with fixture-miss code | Never switch live | `HOLD` |
| Provider 429 | Respect backoff within request and dollar budgets | Bounded | `HOLD` after exhaustion |
| Provider 5xx or timeout | Reconcile idempotency before any paid retry | Bounded | `HOLD` |
| Provider moderation failure | Terminal rejection for output | No bypass retry | `STOP` or `REVIEW` by policy |
| Malformed response | Reject response and retain trace | No uncontrolled retry | `HOLD` |
| Asset digest mismatch | Quarantine bytes | No admission | `STOP` |
| Missing parent or tenant mismatch | Reject contract | None | `STOP` and security alert for tenant mismatch |
| Duplicate | Record duplicate relationship | No quality upgrade | `KEEP` or `STOP` |
| Outcome join failure | Quarantine snapshot | Retry after source correction | `HOLD` |
| Stale outcomes | Display freshness | Wait for complete window | `HOLD` |
| Simulation non-convergence | Mark invalid | May rerun only with predeclared settings | `REVIEW` |
| Learner or mechanism sign disagreement | Show all results | No cherry-picking | `REVIEW` |
| Ledger write failure | Treat decision as uncommitted | Retry ledger only | No outward action |
| Approval service unavailable | Retain draft | Bounded | No write |

## 12. Scaling and efficiency

- Batch same-prompt variations only when they represent the same declared mutation level. Different controlled prompts use bounded concurrency so each request retains its own lineage.
- Screen exact duplicates and inexpensive integrity checks before quality upgrades or tests.
- Use the standard Imagine model for broad exploration and the quality model only for admitted finalists, subject to product evaluation.
- Reuse private file IDs for iterative edits when retention and cost policy permit it.
- Store provider-reported request cost, not only a static price estimate.
- Apply per-tenant, campaign, family, day, call, image, quality-tier, and dollar caps.
- Use backpressure to stop new generation when asset persistence, ledger, or outcome queues are unhealthy.

## 13. Production extensions that require new ADRs

- Event sourcing versus mutable workflow state.
- Production object-store retention, residency, and tenant encryption keys.
- Online versus batch recommendation.
- Outcome attribution and experiment-assignment unit.
- Model fallback and alias-upgrade policy.
- Multi-region failover and consistency.
- Human-approval enforcement and any X Ads draft adapter.
- Ranking-signal export, if ever proposed.

