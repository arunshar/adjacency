# ImagineSignal technical specification

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed implementation contract |
| Author | Arun Sharma |
| Date | 2026-08-05 |
| Compatibility | Python 3.12 and 3.13; existing Adjacency behavior unchanged |

## 1. Package boundary

Create a parallel package rather than extending the existing brand-safety types:

```text
src/adjacency/imagine_signal/
  __init__.py
  contracts.py
  canonical.py
  mutations.py
  gates.py
  decisions.py
  receipts.py
  assets.py
  imagine_client.py
  outcomes.py
  auction.py
  service.py

tests/imagine_signal/
  test_contracts.py
  test_canonical.py
  test_mutations.py
  test_gates.py
  test_decisions.py
  test_receipts.py
  test_assets.py
  test_imagine_client.py
  test_outcomes.py
  test_auction.py
  test_service.py
  test_fixture_replay.py
```

The first pull request should contain only deterministic contracts, hashes, gates, decisions, and tests. Provider, storage, simulator, and UI work should be separate review units.

## 2. Reuse map

| Existing asset | Reuse | Constraint |
|---|---|---|
| `adjacency.contracts.Frozen` pattern | Immutable Pydantic models with `extra="forbid"` | Prefer a shared internal helper only if it does not widen current public contracts |
| `adjacency.contracts._stable_hash` behavior | Canonical JSON plus SHA-256 | Promote or duplicate as a public internal utility only with regression tests |
| `adjacency.gates.GateResult` pattern | Stable code, detail, pass state, coercion concept | New `SignalGateResult`; no reuse of brand-safety `Action` |
| `adjacency.fixtures.FixtureStore` | Secret rejection, canonical request hashes, replay default | Extend through composition for media digests; do not place raw image bytes in JSON fixtures |
| `adjacency.xai.RecordedXAIClient` | Small protocol and explicit record behavior | Imagine uses different endpoints and response shapes; create a new adapter |
| `adjacency.near_dup` | Perceptual image hash, text MinHash, and deterministic clustering | Use as a coarse duplicate screen, not proof of semantic equivalence |
| `adjacency.model_metrics.ModelMeasurement` | Integer cost ticks, response ID, latency, model, and usage fields | Generalize without allowing missing or invalid cost to become zero |
| `adjacency.hitl.HITLQueue` | Review destination protocol | Use only after the decision contract is stable |
| `QUALITY.md` | 100 percent core coverage plus fixture replay for I/O | Add ImagineSignal contracts and gates to the deterministic-core CI command |

## 3. Core enumerations

```text
EvidenceClass:
  PROPOSED
  IMPLEMENTED
  UNIT_TESTED
  FROZEN_REPLAY
  SIMULATED
  SHADOW_ESTIMATE
  RANDOMIZED_DISPLAY_ONLY
  RANDOMIZED_END_TO_END
  SCALED_PRODUCTION

NextAction:
  KEEP
  EDIT
  TEST
  HOLD
  REVIEW
  STOP

DataOrigin:
  SYNTHETIC
  FROZEN_REPLAY
  SHADOW_LOG
  RANDOMIZED_EXPERIMENT
  PRODUCTION

AssetState:
  PLANNED
  GENERATED
  MODERATION_REJECTED
  VERIFIED
  DUPLICATE
  QUARANTINED

Mechanism:
  FIRST_PRICE
  SECOND_PRICE
  SOFT_FLOOR

BidderModel:
  FIXED_BID
  HEDGE
  EXP3_IX
```

Do not add `PROMOTE` until an ADR defines its exact authorization and evidence requirements.

## 4. Immutable contracts

All contracts require `schema_version`, reject undeclared fields, normalize strings where offsets matter, and derive stable hashes from canonical content rather than timestamps.

### `CampaignSpec`

Required fields:

- `schema_version`
- `tenant_id`
- `campaign_id`
- `objective`
- `audience_contexts`
- `measurement_metric`
- `measurement_window`
- `brand_spec_hash`
- `generation_budget`
- `created_by`

The campaign hash excludes mutable processing timestamps but includes every semantic field.

### `BrandSpec`

Required fields:

- `tenant_id`
- `brand_spec_id`
- `required_elements`
- `prohibited_elements`
- `locked_text_claims`
- `locked_product_identity`
- `logo_constraints`
- `source_provenance`

The contract structures the constraints. It does not replace ads-policy or legal validation.

### `MutationSpec`

Required fields:

- `mutation_id`
- `campaign_id`
- `root_asset_id`
- `parent_asset_id`
- `axis`
- `level`
- `locked_attributes`
- `prompt_template_version`
- `prompt_hash`

Invariant: a family has one `axis`; every child has one level on that axis; locked attributes are identical across the family.

The MVP should configure axis strings rather than prematurely claim a universal taxonomy. The demo may choose one axis such as `background_tone`.

### `CreativeAsset`

Required fields:

- `tenant_id`
- `campaign_id`
- `creative_id`
- `root_creative_id`
- `parent_creative_id`
- `mutation_id`
- `request_hash`
- `media_sha256`
- `media_type`
- `width`
- `height`
- `provider`
- `provider_model_requested`
- `provider_model_resolved`
- `provider_request_id`
- `moderation_respected`
- `cost_in_usd_ticks`
- `latency_ms`
- `state`

Provider URLs are transient transport metadata, not identifiers. A verified content digest is mandatory before admission.

### `OutcomeSnapshot`

Required fields:

- `tenant_id`
- `campaign_id`
- `creative_id`
- `context_id`
- `experiment_id`
- `arm_id`
- `origin`
- `measurement_start`
- `measurement_end`
- `attribution_method`
- `impressions`
- `clicks`
- optional aggregate conversions and spend with exact semantics
- `source_snapshot_id`
- `source_sha256`
- `observed_at`

The contract must never call advertiser spend or conversion value "X revenue." If a revenue field is introduced, it must include a `RevenueKind` such as `BILLED_AD_REVENUE`, `ADVERTISER_SPEND`, `ATTRIBUTED_PURCHASE_VALUE`, or `SIMULATED_SELLER_REVENUE`.

### `SignalEstimate`

Required fields:

- `baseline_creative_id`
- `variant_creative_id`
- `context_id`
- `metric`
- `baseline_estimate`
- `variant_estimate`
- `absolute_delta`
- `relative_delta`
- `interval_low`
- `interval_high`
- `method`
- `sample_size`
- `evidence_class`
- `outcome_snapshot_hashes`

Observed, predicted, and simulated values must use distinct metric namespaces.

### `AuctionScenario`

Required fields:

- `scenario_id`
- `scenario_version`
- `query_contexts`
- `query_probabilities`
- `number_of_slots`
- `billing_basis`
- `scoring_rule`
- `mechanism`
- `floor_or_reserve`
- `bid_grid`
- `bidder_types`
- `value_matrices`
- `ctr_matrices`
- `bidder_model`
- `horizon`
- `burn_in`
- `seed`
- `data_origin`
- `known_departures_from_production`

The scenario hash covers all fields that can affect a result.

### `AuctionSensitivityResult`

Required fields:

- `scenario_hash`
- `baseline_signal_hash`
- `variant_signal_hash`
- `common_randomness_id`
- `boundary_crossing_rate`
- `allocation_change_rate`
- `simulated_seller_revenue_baseline`
- `simulated_seller_revenue_variant`
- `simulated_advertiser_utility_baseline`
- `simulated_advertiser_utility_variant`
- `uncertainty`
- `convergence_diagnostics`
- `evidence_class = SIMULATED`

### `DecisionReceipt`

Required fields:

- `receipt_id`
- `receipt_version`
- `tenant_id`
- `campaign_hash`
- `family_hash`
- `asset_hashes`
- `outcome_hashes`
- `scenario_hashes`
- `evidence_class`
- `proposed_action`
- `final_action`
- `gate_results`
- `human_approval`
- `claim_wording`
- `cost_total_ticks`
- `trace_id`
- `created_at`
- `receipt_sha256`

Free-form rationale is display-only and cannot change `final_action`.

## 5. Gate chain

Use `IS` prefixes so these codes cannot be confused with Adjacency's existing G0-G6 API.

| Gate | Purpose | Example failure code | Failure result |
|---|---|---|---|
| `IS0` | Request, schema, mode, and budget integrity | `IS0_BUDGET_EXCEEDED` | `STOP` or `HOLD` |
| `IS1` | Tenant, campaign, parent, and root lineage | `IS1_PARENT_TENANT_MISMATCH` | `STOP` plus security signal |
| `IS2` | Exactly one declared mutation axis and locked constraints | `IS2_UNCONTROLLED_MUTATION` | `REVIEW` or `STOP` |
| `IS3` | Provider completion and moderation admission | `IS3_MODERATION_REJECTED` | `STOP` |
| `IS4` | Asset bytes, media shape, digest, and duplicate integrity | `IS4_ASSET_HASH_MISMATCH` | `STOP` |
| `IS5` | Outcome join, origin, window, freshness, and completeness | `IS5_OUTCOME_STALE` | `HOLD` |
| `IS6` | Statistical and experimental validity | `IS6_INSUFFICIENT_EVIDENCE` | `HOLD` or `TEST` only |
| `IS7` | Auction mechanism, convergence, and learner sensitivity | `IS7_ASSUMPTION_SIGN_CONFLICT` | `REVIEW` |
| `IS8` | Evidence-to-action and claim admission | `IS8_ACTION_EXCEEDS_EVIDENCE` | Coerce to allowed action |

Gate functions are pure. They receive clocks, thresholds, and configuration explicitly. They never call a model, provider, database, or system clock.

### Evidence-to-action ceiling

| Highest evidence | Maximum action in this specification |
|---|---|
| `PROPOSED`, `IMPLEMENTED`, `UNIT_TESTED` | `HOLD`, `REVIEW`, or `STOP` |
| `FROZEN_REPLAY`, `SIMULATED` | `TEST` in a non-production environment |
| `SHADOW_ESTIMATE` | Recommend an authorized experiment, no write |
| `RANDOMIZED_DISPLAY_ONLY` | Recommend a wider display-only test or human-approved draft decision |
| `RANDOMIZED_END_TO_END` | Refer to a separate production launch gate |
| `SCALED_PRODUCTION` | Only actions allowed by the approved launch policy |

The table is a ceiling, not an automatic pass. Lower gates can always reduce the action.

## 6. Internal service API

All mutating calls require `Idempotency-Key`, `X-Tenant-ID`, authenticated actor identity, and an explicit environment mode. The MVP service API changes only ImagineSignal metadata and draft state.

### Create campaign

`POST /v1/imagine-signal/campaigns`

Input: `CampaignSpec` plus inline or referenced `BrandSpec`.

Output: admitted campaign hash, `IS0` and `IS1` results, and current state.

### Plan controlled family

`POST /v1/imagine-signal/campaigns/{campaign_id}/families:plan`

Input: root asset, one axis, mutation levels, locked attributes, provider profile, and family budget.

Output: immutable family plan with request hashes. This call does not contact the provider.

### Generate or replay family

`POST /v1/imagine-signal/families/{family_id}:generate`

Input: expected family version and mode (`fixture` or explicitly authorized `record`).

Output: per-asset status, hashes, cost, moderation metadata, and gate results.

### Ingest aggregate outcomes

`POST /v1/imagine-signal/outcomes:ingest`

Input: signed collection of `OutcomeSnapshot` objects.

Output: accepted, duplicate, quarantined, or rejected entries. At-least-once delivery is deduplicated by source snapshot ID and digest.

### Evaluate family

`POST /v1/imagine-signal/families/{family_id}:evaluate`

Input: expected family version, selected contexts, signal estimator version, optional scenario IDs.

Output: signal estimates, labeled simulations, final action ceiling, and receipt ID.

### Human review

`POST /v1/imagine-signal/decisions/{receipt_id}:review`

Input: expected receipt version, authorized action, reason code, and comment.

Output: append-only receipt revision. An override cannot exceed the actor's authorization or the environment mode.

### Retrieve receipt

`GET /v1/imagine-signal/receipts/{receipt_id}`

Output: complete receipt with evidence references and stable gate codes. Tenant authorization is mandatory.

## 7. Provider client protocol

The provider-independent interface should expose semantic operations, not raw SDK objects:

```python
class ImagineClient(Protocol):
    def generate(self, request: ImageGenerationRequest) -> tuple[GeneratedImage, ...]: ...
    def edit(self, request: ImageEditRequest) -> tuple[GeneratedImage, ...]: ...
```

`GeneratedImage` contains verified bytes or an asset-store handle plus normalized metadata. The rest of the system must not depend on a provider URL.

Implementations:

- `FixtureImagineClient`: replay only; cannot import credentials or live transport.
- `RecordingImagineClient`: explicit record mode; wraps a transport and writes sanitized metadata plus digested blobs.
- A future production client behind the same protocol.

Do not add an automatic live fallback to `FixtureImagineClient`.

## 8. Media fixture format

Existing `FixtureStore` handles JSON. Imagine outputs add binary media. Use two linked records:

```text
fixtures/imagine/api/<surface>/<request_sha256>.json
fixtures/imagine/assets/<media_sha256>.<approved_extension>
```

The JSON stores canonical request fields, request hash, sanitized provider metadata, media digest, byte length, content type, dimensions, and response hash. It does not store credentials, signed URLs, raw base64, or confidential production prompts.

Replay verifies:

1. Surface and request match the path.
2. Request and response metadata hashes match.
3. Asset exists under its digest.
4. Asset bytes match the digest, declared length, media type, and dimensions.
5. Fixture mode has no live transport.

## 9. Auction-sensitivity algorithm

### MVP fixed-bid comparison

For every context `q` and eligible bidder `i`, define the simulated score:

```text
score_i(q) = bid_i * predicted_ctr_i(q)
```

Run baseline and variant with identical bids, competitors, queries, seeds, and pricing settings. Change only the named creative signal for the focal ad. Record whether the focal score crosses the winning boundary, whether allocation changes, and the resulting simulated seller revenue and advertiser utility.

### Research extension

Add Hedge and EXP3-IX exactly as labeled bidder-behavior assumptions. Report their convergence diagnostics and results together. A longer horizon does not automatically resolve disagreement.

### Prohibited shortcut

Do not set observed CTR equal to the ranking system's predicted CTR. If only one is available, name it accurately and restrict the conclusion.

## 10. Test strategy

### Deterministic contract and gate tests

- Unknown fields rejected.
- Hash independent of construction order and non-semantic timestamps.
- Unicode normalization behavior defined.
- Parent existence and tenant match enforced.
- Exactly one family axis enforced.
- Locked attributes cannot drift.
- Evidence ceiling cannot be bypassed by rationale or human text.
- Every gate branch and stable code covered.
- Property tests generate malformed lineages, budgets, windows, and action requests.

### Fixture tests

- Replay succeeds with no credential and a disabled network.
- Missing fixture never calls a provider.
- Request mutation changes fixture key.
- Secret-shaped fields rejected.
- Media corruption and dimension mismatch rejected.
- Temporary and signed URLs absent from committed fixtures.

### Auction tests

- Hand-calculated two-bidder examples.
- Score tie behavior explicit and seeded.
- Common-randomness pairing verified.
- Zero signal produces zero paired score change.
- Boundary crossing occurs only when arithmetic permits it.
- Seller revenue and advertiser utility use separate fields.
- Paper table reproduction is a benchmark, not a hard-coded result.
- Non-convergence and learner disagreement trigger invalid or review states.

### Service tests

- Idempotent create, generate, ingest, evaluate, and review calls.
- Stale version conflicts.
- At-least-once outcome deduplication.
- Ledger failure prevents outward action.
- Mode and feature-flag matrix.
- Tenant isolation and authorization failures.

## 11. CI additions

After the first code slice:

```bash
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/bandit -q -c pyproject.toml -r src
.venv/bin/pytest tests/imagine_signal -q
.venv/bin/pytest tests/imagine_signal/test_contracts.py tests/imagine_signal/test_gates.py \
  --cov=adjacency.imagine_signal.contracts \
  --cov=adjacency.imagine_signal.gates \
  --cov-branch --cov-report=term-missing --cov-fail-under=100
```

The exact coverage syntax must be validated against the installed pytest-cov version before updating CI. The existing package-wide floor remains in force.

## 12. Versioning and compatibility

- Contract changes use explicit schema versions.
- Stable gate codes are a public audit API and cannot be casually reworded.
- Provider aliases are recorded alongside resolved model IDs.
- Re-running a frozen evaluation after code or scenario changes creates a new receipt; it never overwrites the old one.
- A model, mechanism, scoring, attribution, or population change expires dependent claims.
