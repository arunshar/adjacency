# ImagineSignal complete API reference

| Field | Value |
|---|---|
| Version | 1.0 |
| Generated | 2026-08-05 |
| Scope | Every symbol in `src/adjacency/imagine_signal/`, including private helpers |
| Source | Read from the modules themselves, not from runtime introspection |

This is the exhaustive reference. For the narrative, read
[16_MASTER_EXPLAINER.md](16_MASTER_EXPLAINER.md). For the boundary that governs what any of this is
allowed to claim, read [12_IMPLEMENTATION_STATUS.md](12_IMPLEMENTATION_STATUS.md).

Private helpers, the ones prefixed with a single underscore, are included because the user asked for
complete coverage and because several of them carry real invariants. They are marked `private` and
are not part of any compatibility promise.

## Reading order

Modules appear in dependency order. Nothing in an earlier section imports anything from a later one.


| # | Module | Classes | Functions | Methods | Role |
|---:|---|---:|---:|---:|---|
| 1 | [`canonical.py`](#canonicalpy) | 0 | 6 | 0 | Deterministic JSON and content hashing |
| 2 | [`contracts.py`](#contractspy) | 26 | 3 | 29 | Every frozen domain model and enumeration |
| 3 | [`ports.py`](#portspy) | 21 | 0 | 10 | The provider-independent boundary |
| 4 | [`mutations.py`](#mutationspy) | 1 | 4 | 1 | Controlled-family validation |
| 5 | [`assets.py`](#assetspy) | 5 | 4 | 6 | Content-addressed media |
| 6 | [`adapters/fixture_blobs.py`](#adapters-fixture-blobspy) | 7 | 5 | 7 | Replay-first binary fixture store, including the secret scan that refuses to record a credential-shaped string |
| 7 | [`adapters/xai_live.py`](#adapters-xai-livepy) | 4 | 7 | 2 | The live xAI transport |
| 8 | [`imagine_client.py`](#imagine-clientpy) | 8 | 4 | 14 | The three clients and the bounded external-call machinery, including the cost interlock |
| 9 | [`outcomes.py`](#outcomespy) | 7 | 5 | 6 | Aggregate outcome snapshots and their idempotent repository |
| 10 | [`auction.py`](#auctionpy) | 18 | 32 | 7 | Auction sensitivity simulation |
| 11 | [`gates.py`](#gatespy) | 0 | 12 | 0 | `IS0` through `IS8` as pure functions |
| 12 | [`decisions.py`](#decisionspy) | 0 | 5 | 0 | The evidence-to-action ceiling and deterministic action resolution |
| 13 | [`receipts.py`](#receiptspy) | 0 | 5 | 0 | Append-once, digest-linked decision receipts with tamper detection |
| 14 | [`service.py`](#servicepy) | 9 | 11 | 11 | The offline orchestrator |
| 15 | [`demo.py`](#demopy) | 0 | 2 | 0 | Deterministic artifact generation for the reviewed offline demo |
| 16 | [`__init__.py`](#--init--py) | 0 | 0 | 0 | Public package surface |
| 17 | [`adapters/__init__.py`](#adapters---init--py) | 0 | 0 | 0 |  |
| | **Total** | **106** | **105** | **93** | **304 documented entries** |


---

## `canonical.py`

Deterministic JSON and content hashing. Deliberately parallel to the private helper in base Adjacency so ImagineSignal contracts can evolve without moving existing hash vectors.

> Public canonical JSON and content hashing for ImagineSignal.


### Functions


#### `normalize_text`

```python
normalize_text(value: str) -> str
```

`canonical.py:23`


Return the NFC representation used by hashes and string contracts.


#### `_canonical_value` `private`

```python
_canonical_value(value: object) -> object
```

`canonical.py:29`


Raises: `TypeError`, `ValueError`


#### `canonical_json`

```python
canonical_json(value: object) -> str
```

`canonical.py:67`


Serialize a value to deterministic, compact, UTF-8-safe JSON text.


#### `canonical_json_bytes`

```python
canonical_json_bytes(value: object) -> bytes
```

`canonical.py:79`


Return the exact UTF-8 bytes used for content addressing.


#### `content_sha256`

```python
content_sha256(value: object) -> str
```

`canonical.py:85`


Return the lower-case SHA-256 digest of a canonical value.


#### `canonical_payload`

```python
canonical_payload(value: object) -> Any
```

`canonical.py:91`


Expose the normalized JSON-compatible value for artifact writers.


---

## `contracts.py`

Every frozen domain model and enumeration. `extra="forbid"` throughout, so an unknown field is a rejection rather than a silent pass.

> Immutable, versioned contracts for the ImagineSignal bounded context.


### Classes


#### `EvidenceClass`

`contracts.py:20` &nbsp;·&nbsp; bases: `StrEnum`


The provenance class that limits actions and claims.


| Field | Type | Default |
|---|---|---|
| `PROPOSED` | _(assigned)_ | `'PROPOSED'` |
| `IMPLEMENTED` | _(assigned)_ | `'IMPLEMENTED'` |
| `UNIT_TESTED` | _(assigned)_ | `'UNIT_TESTED'` |
| `FROZEN_REPLAY` | _(assigned)_ | `'FROZEN_REPLAY'` |
| `SIMULATED` | _(assigned)_ | `'SIMULATED'` |
| `SHADOW_ESTIMATE` | _(assigned)_ | `'SHADOW_ESTIMATE'` |
| `RANDOMIZED_DISPLAY_ONLY` | _(assigned)_ | `'RANDOMIZED_DISPLAY_ONLY'` |
| `RANDOMIZED_END_TO_END` | _(assigned)_ | `'RANDOMIZED_END_TO_END'` |
| `SCALED_PRODUCTION` | _(assigned)_ | `'SCALED_PRODUCTION'` |



#### `NextAction`

`contracts.py:34` &nbsp;·&nbsp; bases: `StrEnum`


MVP actions. None of these writes to an ads system.


| Field | Type | Default |
|---|---|---|
| `KEEP` | _(assigned)_ | `'KEEP'` |
| `EDIT` | _(assigned)_ | `'EDIT'` |
| `TEST` | _(assigned)_ | `'TEST'` |
| `HOLD` | _(assigned)_ | `'HOLD'` |
| `REVIEW` | _(assigned)_ | `'REVIEW'` |
| `STOP` | _(assigned)_ | `'STOP'` |



#### `DataOrigin`

`contracts.py:45` &nbsp;·&nbsp; bases: `StrEnum`


| Field | Type | Default |
|---|---|---|
| `SYNTHETIC` | _(assigned)_ | `'SYNTHETIC'` |
| `FROZEN_REPLAY` | _(assigned)_ | `'FROZEN_REPLAY'` |
| `SHADOW_LOG` | _(assigned)_ | `'SHADOW_LOG'` |
| `RANDOMIZED_EXPERIMENT` | _(assigned)_ | `'RANDOMIZED_EXPERIMENT'` |
| `PRODUCTION` | _(assigned)_ | `'PRODUCTION'` |



#### `AssetState`

`contracts.py:53` &nbsp;·&nbsp; bases: `StrEnum`


| Field | Type | Default |
|---|---|---|
| `PLANNED` | _(assigned)_ | `'PLANNED'` |
| `GENERATED` | _(assigned)_ | `'GENERATED'` |
| `MODERATION_REJECTED` | _(assigned)_ | `'MODERATION_REJECTED'` |
| `VERIFIED` | _(assigned)_ | `'VERIFIED'` |
| `DUPLICATE` | _(assigned)_ | `'DUPLICATE'` |
| `QUARANTINED` | _(assigned)_ | `'QUARANTINED'` |



#### `Mechanism`

`contracts.py:62` &nbsp;·&nbsp; bases: `StrEnum`


| Field | Type | Default |
|---|---|---|
| `FIRST_PRICE` | _(assigned)_ | `'FIRST_PRICE'` |
| `SECOND_PRICE` | _(assigned)_ | `'SECOND_PRICE'` |
| `SOFT_FLOOR` | _(assigned)_ | `'SOFT_FLOOR'` |



#### `BidderModel`

`contracts.py:68` &nbsp;·&nbsp; bases: `StrEnum`


| Field | Type | Default |
|---|---|---|
| `FIXED_BID` | _(assigned)_ | `'FIXED_BID'` |
| `HEDGE` | _(assigned)_ | `'HEDGE'` |
| `EXP3_IX` | _(assigned)_ | `'EXP3_IX'` |



#### `DeploymentMode`

`contracts.py:74` &nbsp;·&nbsp; bases: `StrEnum`


| Field | Type | Default |
|---|---|---|
| `FIXTURE` | _(assigned)_ | `'fixture'` |
| `RECORD` | _(assigned)_ | `'record'` |
| `SHADOW` | _(assigned)_ | `'shadow'` |
| `DRAFT_BETA` | _(assigned)_ | `'draft_beta'` |
| `EXPERIMENT_DISPLAY_ONLY` | _(assigned)_ | `'experiment_display_only'` |
| `EXPERIMENT_SIGNAL_AWARE` | _(assigned)_ | `'experiment_signal_aware'` |



#### `CostStatus`

`contracts.py:83` &nbsp;·&nbsp; bases: `StrEnum`


| Field | Type | Default |
|---|---|---|
| `EXACT` | _(assigned)_ | `'EXACT'` |
| `ESTIMATED` | _(assigned)_ | `'ESTIMATED'` |
| `UNKNOWN` | _(assigned)_ | `'UNKNOWN'` |



#### `SignalContract`

`contracts.py:116` &nbsp;·&nbsp; bases: `BaseModel`


Base contract: immutable, strict, versioned, and closed to unknown fields.


| Field | Type | Default |
|---|---|---|
| `model_config` | _(assigned)_ | `ConfigDict(frozen=True, extra='forbid', strict=True, validate_default=True)` |
| `schema_version` | `str` | `Field(min_length=1)` |


- **`_nfc_normalize_strings(cls, value: object) -> object`** `@field_validator('*', mode='before')` `@classmethod`

- **`content_hash(self) -> str`** `@property`


#### `GenerationBudget`

`contracts.py:138` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `max_calls` | `int` | `Field(ge=0)` |
| `max_images` | `int` | `Field(ge=0)` |
| `max_quality_images` | `int` | `Field(ge=0)` |
| `max_cost_in_usd_ticks` | `int` | `Field(ge=0)` |
| `max_wallclock_ms` | `int` | `Field(gt=0)` |


- **`_quality_is_within_total(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`


#### `MeasurementWindow`

`contracts.py:152` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `start` | `datetime` | - |
| `end` | `datetime` | - |


- **`_ordered_and_aware(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`


#### `CampaignSpec`

`contracts.py:165` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `tenant_id` | `str` | `Field(min_length=1)` |
| `campaign_id` | `str` | `Field(min_length=1)` |
| `objective` | `str` | `Field(min_length=1)` |
| `audience_contexts` | `tuple[str, ...]` | `Field(min_length=1)` |
| `measurement_metric` | `str` | `Field(min_length=1)` |
| `measurement_window` | `MeasurementWindow` | - |
| `brand_spec_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `generation_budget` | `GenerationBudget` | - |
| `created_by` | `str` | `Field(min_length=1)` |


- **`_contexts_are_unique(self) -> Self`** `@model_validator(mode='after')`

- **`campaign_hash(self) -> str`** `@property`


#### `BrandSpec`

`contracts.py:186` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `tenant_id` | `str` | `Field(min_length=1)` |
| `brand_spec_id` | `str` | `Field(min_length=1)` |
| `required_elements` | `tuple[str, ...]` | `()` |
| `prohibited_elements` | `tuple[str, ...]` | `()` |
| `locked_text_claims` | `tuple[str, ...]` | `()` |
| `locked_product_identity` | `tuple[str, ...]` | `()` |
| `logo_constraints` | `tuple[str, ...]` | `()` |
| `source_provenance` | `tuple[str, ...]` | `Field(min_length=1)` |


- **`_sets_are_unique(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`brand_spec_hash(self) -> str`** `@property`


#### `LockedAttribute`

`contracts.py:217` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `name` | `str` | `Field(min_length=1)` |
| `value_sha256` | `str` | `Field(pattern=SHA256_PATTERN)` |



#### `MutationSpec`

`contracts.py:222` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `tenant_id` | `str` | `Field(min_length=1)` |
| `mutation_id` | `str` | `Field(min_length=1)` |
| `family_id` | `str` | `Field(min_length=1)` |
| `campaign_id` | `str` | `Field(min_length=1)` |
| `root_asset_id` | `str` | `Field(min_length=1)` |
| `parent_asset_id` | `str` | `Field(min_length=1)` |
| `axis` | `str` | `Field(min_length=1)` |
| `level` | `str` | `Field(min_length=1)` |
| `locked_attributes` | `tuple[LockedAttribute, ...]` | `()` |
| `prompt_template_version` | `str` | `Field(min_length=1)` |
| `prompt_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |


- **`_locked_attributes_are_unique(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`mutation_hash(self) -> str`** `@property`


#### `CreativeAsset`

`contracts.py:248` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `tenant_id` | `str` | `Field(min_length=1)` |
| `campaign_id` | `str` | `Field(min_length=1)` |
| `creative_id` | `str` | `Field(min_length=1)` |
| `root_creative_id` | `str` | `Field(min_length=1)` |
| `parent_creative_id` | `str | None` | `Field(default=None, min_length=1)` |
| `mutation_id` | `str | None` | `Field(default=None, min_length=1)` |
| `request_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `media_sha256` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `media_type` | `Literal['image/png', 'image/jpeg']` | - |
| `width` | `int` | `Field(gt=0)` |
| `height` | `int` | `Field(gt=0)` |
| `provider` | `str` | `Field(min_length=1)` |
| `provider_model_requested` | `str` | `Field(min_length=1)` |
| `provider_model_resolved` | `str` | `Field(min_length=1)` |
| `provider_request_id` | `str` | `Field(min_length=1)` |
| `moderation_respected` | `bool` | - |
| `cost_in_usd_ticks` | `int | None` | `Field(default=None, ge=0)` |
| `cost_status` | `CostStatus` | - |
| `latency_ms` | `int` | `Field(ge=0)` |
| `state` | `AssetState` | - |


- **`_lineage_and_cost_are_coherent(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`asset_hash(self) -> str`** `@property`


#### `OutcomeSnapshot`

`contracts.py:294` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `tenant_id` | `str` | `Field(min_length=1)` |
| `campaign_id` | `str` | `Field(min_length=1)` |
| `creative_id` | `str` | `Field(min_length=1)` |
| `context_id` | `str` | `Field(min_length=1)` |
| `experiment_id` | `str` | `Field(min_length=1)` |
| `arm_id` | `str` | `Field(min_length=1)` |
| `origin` | `DataOrigin` | - |
| `measurement_start` | `datetime` | - |
| `measurement_end` | `datetime` | - |
| `attribution_method` | `str` | `Field(min_length=1)` |
| `impressions` | `int` | `Field(ge=0)` |
| `clicks` | `int` | `Field(ge=0)` |
| `conversions` | `int | None` | `Field(default=None, ge=0)` |
| `advertiser_spend_ticks` | `int | None` | `Field(default=None, ge=0)` |
| `attributed_purchase_value_ticks` | `int | None` | `Field(default=None, ge=0)` |
| `source_snapshot_id` | `str` | `Field(min_length=1)` |
| `source_sha256` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `observed_at` | `datetime` | - |


- **`_counts_and_window_are_coherent(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`snapshot_hash(self) -> str`** `@property`


#### `SignalEstimate`

`contracts.py:334` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `baseline_creative_id` | `str` | `Field(min_length=1)` |
| `variant_creative_id` | `str` | `Field(min_length=1)` |
| `context_id` | `str` | `Field(min_length=1)` |
| `metric` | `str` | `Field(min_length=1)` |
| `baseline_estimate` | `float` | - |
| `variant_estimate` | `float` | - |
| `absolute_delta` | `float` | - |
| `relative_delta` | `float | None` | `None` |
| `interval_low` | `float` | - |
| `interval_high` | `float` | - |
| `method` | `str` | `Field(min_length=1)` |
| `sample_size` | `int` | `Field(ge=0)` |
| `evidence_class` | `EvidenceClass` | - |
| `outcome_snapshot_hashes` | `tuple[str, ...]` | `Field(min_length=1)` |


- **`_estimate_is_coherent(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`signal_hash(self) -> str`** `@property`


#### `AuctionScenarioRecord`

`contracts.py:386` &nbsp;·&nbsp; bases: `SignalContract`


Canonical disclosure record for a runtime auction scenario.


| Field | Type | Default |
|---|---|---|
| `scenario_id` | `str` | `Field(min_length=1)` |
| `scenario_version` | `str` | `Field(min_length=1)` |
| `query_contexts` | `tuple[str, ...]` | `Field(min_length=1)` |
| `query_probabilities` | `tuple[float, ...]` | `Field(min_length=1)` |
| `number_of_slots` | `int` | `Field(gt=0)` |
| `billing_basis` | `str` | `Field(min_length=1)` |
| `scoring_rule` | `str` | `Field(min_length=1)` |
| `mechanism` | `Mechanism` | - |
| `floor_or_reserve` | `float` | `Field(ge=0.0)` |
| `bid_grid` | `tuple[float, ...]` | `Field(min_length=1)` |
| `bidder_types` | `tuple[str, ...]` | `Field(min_length=1)` |
| `value_matrices` | `tuple[tuple[float, ...], ...]` | `Field(min_length=1)` |
| `ctr_matrices` | `tuple[tuple[float, ...], ...]` | `Field(min_length=1)` |
| `bidder_model` | `BidderModel` | - |
| `horizon` | `int` | `Field(gt=0)` |
| `burn_in` | `int` | `Field(ge=0)` |
| `seed` | `int` | `Field(ge=0)` |
| `data_origin` | `DataOrigin` | - |
| `known_departures_from_production` | `tuple[str, ...]` | `Field(min_length=1)` |


- **`_scenario_dimensions_are_coherent(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`scenario_hash(self) -> str`** `@property`


#### `UncertaintyInterval`

`contracts.py:449` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `low` | `float` | - |
| `high` | `float` | - |
| `method` | `str` | `Field(min_length=1)` |


- **`_ordered_and_finite(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`


#### `ConvergenceRecord`

`contracts.py:463` &nbsp;·&nbsp; bases: `SignalContract`


Canonical convergence disclosure emitted by the runtime simulator.


| Field | Type | Default |
|---|---|---|
| `converged` | `bool` | - |
| `iterations` | `int` | `Field(ge=0)` |
| `stability_metric` | `float | None` | `None` |
| `notes` | `tuple[str, ...]` | `()` |


- **`_stability_is_finite(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`


#### `AuctionSensitivityRecord`

`contracts.py:478` &nbsp;·&nbsp; bases: `SignalContract`


Receipt-bound summary converted from a complete runtime simulation result.


| Field | Type | Default |
|---|---|---|
| `scenario_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `baseline_signal_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `variant_signal_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `common_randomness_id` | `str` | `Field(min_length=1)` |
| `mechanism` | `Mechanism` | - |
| `bidder_model` | `BidderModel` | - |
| `boundary_crossing_rate` | `float` | `Field(ge=0.0, le=1.0)` |
| `allocation_change_rate` | `float` | `Field(ge=0.0, le=1.0)` |
| `simulated_seller_revenue_baseline` | `float` | - |
| `simulated_seller_revenue_variant` | `float` | - |
| `simulated_advertiser_utility_baseline` | `float` | - |
| `simulated_advertiser_utility_variant` | `float` | - |
| `uncertainty` | `UncertaintyInterval` | - |
| `convergence_diagnostics` | `ConvergenceRecord` | - |
| `evidence_class` | `EvidenceClass` | `EvidenceClass.SIMULATED` |


- **`_result_is_simulated_and_finite(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`result_hash(self) -> str`** `@property`


#### `SignalGateResult`

`contracts.py:516` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `gate` | `str` | `Field(pattern=GATE_PATTERN)` |
| `passed` | `bool` | - |
| `code` | `str` | `Field(pattern=GATE_CODE_PATTERN)` |
| `detail` | `str` | `''` |
| `coerce_to` | `NextAction | None` | `None` |
| `security_signal` | `bool` | `False` |


- **`_gate_code_and_outcome_are_coherent(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`__bool__(self) -> bool`**


#### `HumanApproval`

`contracts.py:542` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `approval_id` | `str` | `Field(min_length=1)` |
| `receipt_id` | `str` | `Field(min_length=1)` |
| `previous_receipt_sha256` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `actor_id` | `str` | `Field(min_length=1)` |
| `authorized_action` | `NextAction` | - |
| `reason_code` | `str` | `Field(min_length=1)` |
| `comment` | `str` | `''` |
| `approved_at` | `datetime` | - |


- **`_approval_time_is_aware(self) -> Self`** `@model_validator(mode='after')`


#### `SignalDecision`

`contracts.py:558` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `evidence_class` | `EvidenceClass` | - |
| `proposed_action` | `NextAction` | - |
| `final_action` | `NextAction` | - |
| `gate_results` | `tuple[SignalGateResult, ...]` | `Field(min_length=1)` |
| `claim_wording` | `str` | `Field(min_length=1)` |
| `rationale` | `str` | `''` |


- **`_decision_matches_the_gate_chain(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`decision_hash(self) -> str`** `@property`


#### `DecisionReceipt`

`contracts.py:596` &nbsp;·&nbsp; bases: `SignalContract`


| Field | Type | Default |
|---|---|---|
| `receipt_id` | `str` | `Field(min_length=1)` |
| `receipt_version` | `int` | `Field(ge=1)` |
| `previous_receipt_sha256` | `str | None` | `Field(default=None, pattern=SHA256_PATTERN)` |
| `tenant_id` | `str` | `Field(min_length=1)` |
| `campaign_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `family_hash` | `str` | `Field(pattern=SHA256_PATTERN)` |
| `asset_hashes` | `tuple[str, ...]` | `Field(min_length=1)` |
| `outcome_hashes` | `tuple[str, ...]` | `()` |
| `scenario_hashes` | `tuple[str, ...]` | `()` |
| `evidence_class` | `EvidenceClass` | - |
| `proposed_action` | `NextAction` | - |
| `final_action` | `NextAction` | - |
| `gate_results` | `tuple[SignalGateResult, ...]` | `Field(min_length=1)` |
| `human_approval` | `HumanApproval | None` | `None` |
| `claim_wording` | `str` | `Field(min_length=1)` |
| `cost_total_ticks` | `int | None` | `Field(default=None, ge=0)` |
| `cost_status` | `CostStatus` | - |
| `trace_id` | `str` | `Field(min_length=1)` |
| `created_at` | `datetime` | - |
| `receipt_sha256` | `str` | `Field(pattern=SHA256_PATTERN)` |


- **`_receipt_is_coherent(self) -> Self`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`content_hash(self) -> str`** `@property`


### Functions


#### `_normalize_strings` `private`

```python
_normalize_strings(value: object) -> object
```

`contracts.py:89`


#### `_require_aware` `private`

```python
_require_aware(value: datetime, field_name: str) -> None
```

`contracts.py:106`


Raises: `ValueError`


#### `_require_unique` `private`

```python
_require_unique(values: tuple[str, ...], field_name: str) -> None
```

`contracts.py:111`


Raises: `ValueError`


---

## `ports.py`

The provider-independent boundary. Contains no HTTP client, no credential lookup, and no environment switch. This is the file that makes the whole package testable without a network.

> Provider-independent contracts for the Imagine boundary.


### Classes


#### `ImagineMode`

`ports.py:20` &nbsp;·&nbsp; bases: `StrEnum`


Execution modes ordered by increasing external effect.


| Field | Type | Default |
|---|---|---|
| `REPLAY` | _(assigned)_ | `'replay'` |
| `RECORD` | _(assigned)_ | `'record'` |
| `LIVE` | _(assigned)_ | `'live'` |



#### `ImageOperation`

`ports.py:28` &nbsp;·&nbsp; bases: `StrEnum`


Semantic operations exposed by the provider-independent client.


| Field | Type | Default |
|---|---|---|
| `GENERATE` | _(assigned)_ | `'generate'` |
| `EDIT` | _(assigned)_ | `'edit'` |



#### `ProviderCallState`

`ports.py:35` &nbsp;·&nbsp; bases: `StrEnum`


Normalized provider completion state.


| Field | Type | Default |
|---|---|---|
| `COMPLETED` | _(assigned)_ | `'COMPLETED'` |
| `MODERATION_REJECTED` | _(assigned)_ | `'MODERATION_REJECTED'` |
| `UNKNOWN` | _(assigned)_ | `'UNKNOWN'` |



#### `ResponseOrigin`

`ports.py:43` &nbsp;·&nbsp; bases: `StrEnum`


How normalized response evidence was produced.


| Field | Type | Default |
|---|---|---|
| `SYNTHETIC_FIXTURE` | _(assigned)_ | `'SYNTHETIC_FIXTURE'` |
| `PROVIDER_RECORDING` | _(assigned)_ | `'PROVIDER_RECORDING'` |
| `LIVE_PROVIDER` | _(assigned)_ | `'LIVE_PROVIDER'` |



#### `CostStatus`

`ports.py:51` &nbsp;·&nbsp; bases: `StrEnum`


Whether provider cost is an exact reported value.


| Field | Type | Default |
|---|---|---|
| `KNOWN` | _(assigned)_ | `'KNOWN'` |
| `UNKNOWN` | _(assigned)_ | `'UNKNOWN'` |



#### `BudgetStatus`

`ports.py:58` &nbsp;·&nbsp; bases: `StrEnum`


Post-call cost admission state.


| Field | Type | Default |
|---|---|---|
| `WITHIN_LIMIT` | _(assigned)_ | `'WITHIN_LIMIT'` |
| `EXCEEDED` | _(assigned)_ | `'EXCEEDED'` |
| `UNKNOWN` | _(assigned)_ | `'UNKNOWN'` |



#### `FrozenAdapterModel`

`ports.py:66` &nbsp;·&nbsp; bases: `BaseModel`


Immutable, closed model used only at the Imagine adapter boundary.


| Field | Type | Default |
|---|---|---|
| `model_config` | _(assigned)_ | `ConfigDict(frozen=True, extra='forbid')` |



#### `CostMeasurement`

`ports.py:72` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Exact integer ticks or an explicit unknown value.


| Field | Type | Default |
|---|---|---|
| `status` | `CostStatus` | - |
| `ticks` | `int | None` | `Field(default=None, ge=0)` |


- **`_status_matches_ticks(self) -> CostMeasurement`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`

- **`known(cls, ticks: int) -> CostMeasurement`** `@classmethod`

- **`unknown(cls) -> CostMeasurement`** `@classmethod`


#### `ImageReference`

`ports.py:98` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Verified input-media identity for an edit request.


| Field | Type | Default |
|---|---|---|
| `media_sha256` | `str` | `Field(pattern='^[0-9a-f]{64}$')` |
| `media_type` | `str` | `Field(pattern='^image/(png|jpeg)$')` |
| `width` | `int` | `Field(gt=0)` |
| `height` | `int` | `Field(gt=0)` |
| `provider_file_id` | `str | None` | `Field(default=None, min_length=1)` |



#### `_ImageRequest` `private`

`ports.py:108` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


| Field | Type | Default |
|---|---|---|
| `schema_version` | `str` | `Field(min_length=1)` |
| `model` | `str` | `Field(min_length=1)` |
| `prompt` | `str` | `Field(min_length=1, max_length=20000)` |
| `n` | `int` | `Field(default=1, ge=1, le=MAX_OUTPUTS_PER_CALL)` |
| `aspect_ratio` | `str` | `Field(default='1:1', min_length=1)` |
| `resolution` | `str` | `Field(default='1k', pattern='^(1k|2k)$')` |
| `data_classification` | `str` | `Field(default='synthetic', pattern='^(synthetic|non_sensitive_demo)$')` |


- **`_normalize_text(cls, value: str) -> str`** `@field_validator('model', 'prompt', 'aspect_ratio')` `@classmethod`
  <br/>Raises: `ValueError`


#### `ImageGenerationRequest`

`ports.py:129` &nbsp;·&nbsp; bases: `_ImageRequest`


A bounded text-to-image request.



#### `ImageEditRequest`

`ports.py:133` &nbsp;·&nbsp; bases: `_ImageRequest`


A bounded edit request referencing already verified inputs.


| Field | Type | Default |
|---|---|---|
| `references` | `tuple[ImageReference, ...]` | `Field(min_length=1, max_length=MAX_REFERENCE_IMAGES)` |



#### `GeneratedImage`

`ports.py:145` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Verified durable media identity returned to the application.


| Field | Type | Default |
|---|---|---|
| `ordinal` | `int` | `Field(ge=0)` |
| `media_sha256` | `str` | `Field(pattern='^[0-9a-f]{64}$')` |
| `media_type` | `str` | `Field(pattern='^image/(png|jpeg)$')` |
| `width` | `int` | `Field(gt=0)` |
| `height` | `int` | `Field(gt=0)` |
| `byte_length` | `int` | `Field(gt=0)` |
| `blob_path` | `str` | `Field(min_length=1)` |



#### `ImagineResponseMetadata`

`ports.py:157` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Strict response fields permitted in a replay fixture.


| Field | Type | Default |
|---|---|---|
| `state` | `ProviderCallState` | - |
| `response_origin` | `ResponseOrigin` | - |
| `generator_id` | `str | None` | `Field(default=None, min_length=1)` |
| `provider_request_id` | `str | None` | `Field(default=None, min_length=1)` |
| `provider_model_requested` | `str` | `Field(min_length=1)` |
| `provider_model_resolved` | `str | None` | `Field(default=None, min_length=1)` |
| `moderation_respected` | `bool | None` | `None` |
| `cost` | `CostMeasurement` | - |
| `budget_status` | `BudgetStatus` | - |
| `latency_ms` | `int | None` | `Field(default=None, ge=0)` |
| `error_code` | `str | None` | `Field(default=None, min_length=1)` |


- **`_origin_has_provenance(self) -> ImagineResponseMetadata`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`


#### `ImagineCallResult`

`ports.py:179` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Normalized call result for replay, recording, or live execution.


| Field | Type | Default |
|---|---|---|
| `mode` | `ImagineMode` | - |
| `operation` | `ImageOperation` | - |
| `state` | `ProviderCallState` | - |
| `response_origin` | `ResponseOrigin` | - |
| `generator_id` | `str | None` | `Field(default=None, min_length=1)` |
| `request_sha256` | `str` | `Field(pattern='^[0-9a-f]{64}$')` |
| `response_sha256` | `str | None` | `Field(default=None, pattern='^[0-9a-f]{64}$')` |
| `provider_request_id` | `str | None` | `Field(default=None, min_length=1)` |
| `provider_model_requested` | `str` | `Field(min_length=1)` |
| `provider_model_resolved` | `str | None` | `Field(default=None, min_length=1)` |
| `moderation_respected` | `bool | None` | `None` |
| `cost` | `CostMeasurement` | - |
| `budget_status` | `BudgetStatus` | - |
| `latency_ms` | `int | None` | `Field(default=None, ge=0)` |
| `images` | `tuple[GeneratedImage, ...]` | `()` |
| `error_code` | `str | None` | `Field(default=None, min_length=1)` |


- **`_completion_shape(self) -> ImagineCallResult`** `@model_validator(mode='after')`
  <br/>Raises: `ValueError`


#### `ExternalCallPolicy`

`ports.py:215` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Explicit, bounded authorization required for any external invocation.


| Field | Type | Default |
|---|---|---|
| `approved` | `bool` | `False` |
| `max_calls` | `int` | `Field(default=1, ge=1, le=100)` |
| `max_outputs_per_call` | `int` | `Field(default=1, ge=1, le=MAX_OUTPUTS_PER_CALL)` |
| `max_total_cost_ticks` | `int` | `Field(ge=0)` |



#### `TransportImage`

`ports.py:225`


Downloaded or decoded provider media awaiting validation.


| Field | Type | Default |
|---|---|---|
| `media_bytes` | `bytes` | - |
| `declared_content_type` | `str | None` | `None` |
| `declared_width` | `int | None` | `None` |
| `declared_height` | `int | None` | `None` |
| `expected_sha256` | `str | None` | `None` |



#### `TransportResult`

`ports.py:236`


Typed result returned by an injected provider transport.


| Field | Type | Default |
|---|---|---|
| `state` | `ProviderCallState` | - |
| `images` | `tuple[TransportImage, ...]` | `()` |
| `provider_request_id` | `str | None` | `None` |
| `provider_model_resolved` | `str | None` | `None` |
| `moderation_respected` | `bool | None` | `None` |
| `cost` | `CostMeasurement` | `CostMeasurement(status=CostStatus.UNKNOWN)` |
| `latency_ms` | `int | None` | `None` |
| `error_code` | `str | None` | `None` |



#### `ProviderOutcomeUnknownError`

`ports.py:249` &nbsp;·&nbsp; bases: `RuntimeError`


The provider may have accepted work, but completion cannot be reconciled.


- **`__init__(self, message: str, *, provider_request_id: str | None = None) -> None`**


#### `ImagineTransport`

`ports.py:257` &nbsp;·&nbsp; bases: `Protocol`


Injected transport that performs exactly one provider operation.


- **`invoke(self, *, operation: ImageOperation, request: ImagineRequest) -> TransportResult`**
  <br/>Invoke once. Retry and fallback are intentionally absent.


#### `ImagineClient`

`ports.py:269` &nbsp;·&nbsp; bases: `Protocol`


Provider-independent image generation interface.


- **`generate(self, request: ImageGenerationRequest) -> ImagineCallResult`**
  <br/>Generate or replay images.

- **`edit(self, request: ImageEditRequest) -> ImagineCallResult`**
  <br/>Edit or replay images.


---

## `mutations.py`

Controlled-family validation. Proves exactly one declared axis changed and that every locked attribute is byte-identical.

> Deterministic planning and validation for one-atom creative mutations.


### Classes


#### `MutationValidation`

`mutations.py:14`


Machine-readable result for a controlled-family validation.


| Field | Type | Default |
|---|---|---|
| `passed` | `bool` | - |
| `codes` | `tuple[str, ...]` | `()` |
| `details` | `tuple[str, ...]` | `()` |


- **`__bool__(self) -> bool`**


### Functions


#### `_add_issue` `private`

```python
_add_issue(codes: list[str], details: list[str], code: str, detail: str) -> None
```

`mutations.py:25`


#### `family_hash`

```python
family_hash(mutations: Sequence[MutationSpec]) -> str
```

`mutations.py:36`


Hash a family independently of caller-provided sequence order.


Raises: `ValueError`


#### `plan_controlled_mutations`

```python
plan_controlled_mutations(*, schema_version: str, tenant_id: str, family_id: str, campaign_id: str, root_asset_id: str, parent_asset_id: str, axis: str, levels: tuple[str, ...], locked_attributes: tuple[LockedAttribute, ...], prompt_template_version: str, prompt_template: str) -> tuple[MutationSpec, ...]
```

`mutations.py:48`


Compile two to four levels into deterministic one-axis mutation specs.


Raises: `ValueError`


#### `validate_controlled_family`

```python
validate_controlled_family(mutations: Sequence[MutationSpec], *, observed_changes: Mapping[str, Collection[str]] | None = None, observed_locked_hashes: Mapping[str, Mapping[str, str]] | None = None) -> MutationValidation
```

`mutations.py:127`


Validate declaration consistency and optional post-generation observations.


---

## `assets.py`

Content-addressed media. Parses PNG and JPEG headers by hand, so there is no Pillow dependency in the core.

> Content-addressed image validation and local blob persistence.


### Classes


#### `AssetValidationError`

`assets.py:37` &nbsp;·&nbsp; bases: `ValueError`


Raised when untrusted media cannot be admitted.


- **`__init__(self, code: str, detail: str) -> None`**


#### `AssetPolicy`

`assets.py:46` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Hard limits applied before media admission.


| Field | Type | Default |
|---|---|---|
| `max_bytes` | `int` | `Field(default=20 * 1024 * 1024, gt=0)` |
| `max_width` | `int` | `Field(default=8192, gt=0)` |
| `max_height` | `int` | `Field(default=8192, gt=0)` |
| `max_pixels` | `int` | `Field(default=8192 * 8192, gt=0)` |
| `approved_content_types` | `tuple[str, ...]` | `('image/png', 'image/jpeg')` |



#### `AssetDescriptor`

`assets.py:56` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Immutable identity and verified shape for one media blob.


| Field | Type | Default |
|---|---|---|
| `media_sha256` | `str` | `Field(pattern='^[0-9a-f]{64}$')` |
| `byte_length` | `int` | `Field(gt=0)` |
| `content_type` | `str` | `Field(pattern='^image/(png|jpeg)$')` |
| `width` | `int` | `Field(gt=0)` |
| `height` | `int` | `Field(gt=0)` |
| `extension` | `str` | `Field(pattern='^(png|jpg)$')` |



#### `StoredAsset`

`assets.py:67` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Verified descriptor plus its local durable path.


| Field | Type | Default |
|---|---|---|
| `descriptor` | `AssetDescriptor` | - |
| `path` | `str` | `Field(min_length=1)` |



#### `ContentAddressedAssetStore`

`assets.py:173`


Write-once local image store keyed by verified byte digest.


- **`__init__(self, root: Path | str, *, policy: AssetPolicy | None = None) -> None`**

- **`validate(self, media_bytes: bytes, *, declared_content_type: str | None = None, declared_width: int | None = None, declared_height: int | None = None, expected_sha256: str | None = None, expected_byte_length: int | None = None) -> AssetDescriptor`**
  <br/>Validate bytes, declarations, dimensions, and digest without writing.
  <br/>Raises: `AssetValidationError`

- **`path_for(self, descriptor: AssetDescriptor) -> Path`**
  <br/>Resolve a descriptor to its digest-derived path.

- **`put(self, media_bytes: bytes, *, declared_content_type: str | None = None, declared_width: int | None = None, declared_height: int | None = None, expected_sha256: str | None = None, expected_byte_length: int | None = None) -> StoredAsset`**
  <br/>Validate and persist one blob atomically.

- **`read_verified(self, descriptor: AssetDescriptor) -> bytes`**
  <br/>Read a stored blob and recheck every declared property.
  <br/>Raises: `AssetValidationError`


### Functions


#### `media_sha256`

```python
media_sha256(media_bytes: bytes) -> str
```

`assets.py:74`


Return the byte-exact SHA-256 digest for media.


#### `_png_dimensions` `private`

```python
_png_dimensions(media_bytes: bytes) -> tuple[int, int]
```

`assets.py:80`


Raises: `AssetValidationError`


#### `_jpeg_dimensions` `private`

```python
_jpeg_dimensions(media_bytes: bytes) -> tuple[int, int]
```

`assets.py:120`


Raises: `AssetValidationError`


#### `inspect_media`

```python
inspect_media(media_bytes: bytes) -> tuple[str, str, int, int]
```

`assets.py:161`


Identify an approved image using magic bytes and read its dimensions.


Raises: `AssetValidationError`


---

## `adapters/fixture_blobs.py`

Replay-first binary fixture store, including the secret scan that refuses to record a credential-shaped string.

> Replay-first JSON metadata and digest-linked binary image fixtures.


### Classes


#### `BinaryFixtureError`

`adapters/fixture_blobs.py:82` &nbsp;·&nbsp; bases: `RuntimeError`


Base error for binary fixture operations.



#### `BinaryFixtureMissError`

`adapters/fixture_blobs.py:86` &nbsp;·&nbsp; bases: `BinaryFixtureError, FileNotFoundError`


Replay could not find the exact canonical request.



#### `BinaryFixtureCorruptError`

`adapters/fixture_blobs.py:90` &nbsp;·&nbsp; bases: `BinaryFixtureError, ValueError`


Fixture metadata or linked media failed verification.



#### `BinaryFixtureSecretError`

`adapters/fixture_blobs.py:94` &nbsp;·&nbsp; bases: `BinaryFixtureError, ValueError`


Request or response metadata contains prohibited secret material.



#### `BinaryFixtureConflictError`

`adapters/fixture_blobs.py:98` &nbsp;·&nbsp; bases: `BinaryFixtureError`


A write attempted to change an immutable request fixture.



#### `FixtureRecord`

`adapters/fixture_blobs.py:102` &nbsp;·&nbsp; bases: `FrozenAdapterModel`


Verified fixture data returned to the replay client.


| Field | Type | Default |
|---|---|---|
| `surface` | `str` | `Field(pattern='^[a-z0-9][a-z0-9_.-]*$')` |
| `request_sha256` | `str` | `Field(pattern='^[0-9a-f]{64}$')` |
| `response_sha256` | `str` | `Field(pattern='^[0-9a-f]{64}$')` |
| `response_metadata` | `dict[str, Any]` | - |
| `assets` | `tuple[StoredAsset, ...]` | - |
| `fixture_path` | `str` | `Field(min_length=1)` |



#### `BinaryFixtureStore`

`adapters/fixture_blobs.py:183`


Content-addressed replay store for sanitized metadata and image blobs.


- **`__init__(self, root: Path | str = 'fixtures/imagine_signal', *, asset_store: ContentAddressedAssetStore | None = None) -> None`**

- **`_validate_surface(surface: str) -> None`** `@staticmethod`
  <br/>Raises: `ValueError`

- **`request_hash(self, surface: str, request: Any) -> str`**
  <br/>Return the canonical fixture identity after request secret scanning.

- **`fixture_path(self, surface: str, request: Any) -> Path`**
  <br/>Resolve the immutable metadata path for a request.

- **`record(self, *, surface: str, request: Any, response_metadata: Mapping[str, Any], images: Sequence[TransportImage]) -> FixtureRecord`**
  <br/>Validate and atomically record one response and its linked media.
  <br/>Raises: `BinaryFixtureConflictError`, `BinaryFixtureCorruptError`

- **`replay(self, *, surface: str, request: Any) -> FixtureRecord`**
  <br/>Replay the exact request, verifying metadata and every linked blob.
  <br/>Raises: `BinaryFixtureCorruptError`, `BinaryFixtureMissError`

- **`_write_atomic(path: Path, document: dict[str, Any]) -> None`** `@staticmethod`
  <br/>Raises: `BinaryFixtureConflictError`, `BinaryFixtureCorruptError`


### Functions


#### `_jsonable` `private`

```python
_jsonable(value: Any) -> Any
```

`adapters/fixture_blobs.py:113`


Raises: `TypeError`


#### `canonical_json`

```python
canonical_json(value: Any) -> str
```

`adapters/fixture_blobs.py:131`


Serialize fixture metadata in its byte-stable form.


#### `metadata_sha256`

```python
metadata_sha256(value: Any) -> str
```

`adapters/fixture_blobs.py:143`


Hash canonical JSON metadata.


#### `reject_fixture_secrets`

```python
reject_fixture_secrets(value: Any, *, path: str) -> None
```

`adapters/fixture_blobs.py:149`


Recursively reject credential, raw media, and temporary URL material.


Raises: `BinaryFixtureSecretError`


#### `_validate_response_allowlist` `private`

```python
_validate_response_allowlist(value: Any, *, fixture_path: Path | None = None) -> None
```

`adapters/fixture_blobs.py:175`


Raises: `BinaryFixtureCorruptError`


---

## `adapters/xai_live.py`

The live xAI transport. SKELETON: two functions raise `NotImplementedError` on purpose because the provider field names are UNVERIFIED and were not guessed.

> Skeleton xAI Imagine transport for the Grokathon live slice.


### Classes


#### `ProviderImagePayload`

`adapters/xai_live.py:110`


One decoded provider image, already fetched into memory.


| Field | Type | Default |
|---|---|---|
| `media_bytes` | `bytes` | - |
| `declared_content_type` | `str | None` | `None` |
| `declared_width` | `int | None` | `None` |
| `declared_height` | `int | None` | `None` |
| `expected_sha256` | `str | None` | `None` |



#### `ProviderResponsePayload`

`adapters/xai_live.py:127`


Normalized provider response, independent of xAI JSON field names.


| Field | Type | Default |
|---|---|---|
| `state` | `ProviderCallState` | - |
| `images` | `tuple[ProviderImagePayload, ...]` | `()` |
| `provider_request_id` | `str | None` | `None` |
| `provider_model_resolved` | `str | None` | `None` |
| `moderation_respected` | `bool | None` | `None` |
| `cost_ticks` | `int | None` | `None` |
| `latency_ms` | `int | None` | `None` |
| `error_code` | `str | None` | `None` |



#### `HttpCallable`

`adapters/xai_live.py:144` &nbsp;·&nbsp; bases: `Protocol`


Injected HTTP surface. Performs exactly one request and returns JSON.


- **`__call__(self, *, method: str, url: str, json_body: dict[str, object]) -> dict[str, object]`**
  <br/>Issue one authorized request. Retry and fallback are intentionally absent.


#### `XAIImagineTransport`

`adapters/xai_live.py:299`


Injected-HTTP xAI transport satisfying the ImagineTransport protocol.


| Field | Type | Default |
|---|---|---|
| `http` | `HttpCallable` | - |
| `base_url` | `str` | `XAI_API_BASE` |
| `calls_made` | `int` | `field(default=0, init=False)` |


- **`invoke(self, *, operation: ImageOperation, request: ImagineRequest) -> TransportResult`**
  <br/>Invoke once.
  <br/>Raises: `NotImplementedError`


### Functions


#### `usd_to_ticks`

```python
usd_to_ticks(usd: float) -> int
```

`adapters/xai_live.py:68`


Convert a US dollar cap into the provider's integer tick unit.


Raises: `ValueError`


#### `ticks_to_usd`

```python
ticks_to_usd(ticks: int) -> float
```

`adapters/xai_live.py:79`


Convert provider ticks back to US dollars for a human-readable ledger.


Raises: `ValueError`


#### `endpoint_for`

```python
endpoint_for(operation: ImageOperation, *, base: str = XAI_API_BASE) -> str
```

`adapters/xai_live.py:168`


Return the full endpoint URL for a semantic operation.


Raises: `ValueError`


#### `build_request_body`

```python
build_request_body(request: ImagineRequest) -> dict[str, object]
```

`adapters/xai_live.py:178`


Build the provider request body from a validated ImagineSignal request.


#### `map_provider_response`

```python
map_provider_response(payload: ProviderResponsePayload) -> TransportResult
```

`adapters/xai_live.py:215`


Map a normalized provider payload onto the ImagineSignal transport result.


#### `extract_provider_response`

```python
extract_provider_response(raw: dict[str, object], *, latency_ms: int) -> ProviderResponsePayload
```

`adapters/xai_live.py:255`


Translate a raw xAI JSON response into the normalized payload.


Raises: `NotImplementedError`


#### `is_generation`

```python
is_generation(request: ImagineRequest) -> bool
```

`adapters/xai_live.py:349`


Return whether a request is a text-to-image generation rather than an edit.


---

## `imagine_client.py`

The three clients and the bounded external-call machinery, including the cost interlock.

> Replay-first Grok Imagine client with explicit external-call authorization.


### Classes


#### `ImagineClientError`

`imagine_client.py:41` &nbsp;·&nbsp; bases: `RuntimeError`


Base error for Imagine adapter failures.



#### `ImagineConfigurationError`

`imagine_client.py:45` &nbsp;·&nbsp; bases: `ImagineClientError`


Client mode or external authorization is invalid.



#### `ImagineResponseError`

`imagine_client.py:49` &nbsp;·&nbsp; bases: `ImagineClientError`


Provider response does not satisfy the normalized contract.



#### `ImagineCallBudgetError`

`imagine_client.py:53` &nbsp;·&nbsp; bases: `ImagineClientError`


No further external call is permitted by the configured budget.



#### `FixtureImagineClient`

`imagine_client.py:114`


Credential-free client that only replays exact committed fixtures.


| Field | Type | Default |
|---|---|---|
| `mode` | _(assigned)_ | `ImagineMode.REPLAY` |


- **`__init__(self, fixture_store: BinaryFixtureStore | None = None) -> None`**

- **`generate(self, request: ImageGenerationRequest) -> ImagineCallResult`**

- **`edit(self, request: ImageEditRequest) -> ImagineCallResult`**

- **`_replay(self, operation: ImageOperation, request: ImagineRequest) -> ImagineCallResult`**


#### `_ExternalImagineClient` `private`

`imagine_client.py:138`


Single-provider client with bounded calls and no retry or fallback path.


- **`__init__(self, *, mode: ImagineMode, transport: ImagineTransport, policy: ExternalCallPolicy, fixture_store: BinaryFixtureStore | None = None, asset_store: ContentAddressedAssetStore | None = None) -> None`**
  <br/>Raises: `ImagineConfigurationError`

- **`generate(self, request: ImageGenerationRequest) -> ImagineCallResult`**

- **`edit(self, request: ImageEditRequest) -> ImagineCallResult`**

- **`_admit_call(self, request: ImagineRequest) -> None`**
  <br/>Raises: `ImagineCallBudgetError`

- **`_cost_status(self, cost: CostMeasurement) -> BudgetStatus`**
  <br/>Raises: `ImagineResponseError`

- **`_invoke(self, operation: ImageOperation, request: ImagineRequest) -> ImagineCallResult`**
  <br/>Raises: `ImagineConfigurationError`

- **`_validate_transport_result(result: TransportResult, request: ImagineRequest) -> None`** `@staticmethod`
  <br/>Raises: `ImagineResponseError`

- **`_store_live_assets(self, images: tuple[TransportImage, ...]) -> tuple[StoredAsset, ...]`**
  <br/>Raises: `ImagineConfigurationError`


#### `RecordingImagineClient`

`imagine_client.py:382` &nbsp;·&nbsp; bases: `_ExternalImagineClient`


Explicit bounded external client that records sanitized fixtures.


- **`__init__(self, *, transport: ImagineTransport, policy: ExternalCallPolicy, fixture_store: BinaryFixtureStore) -> None`**


#### `LiveImagineClient`

`imagine_client.py:400` &nbsp;·&nbsp; bases: `_ExternalImagineClient`


Explicit bounded client that validates outputs without recording metadata.


- **`__init__(self, *, transport: ImagineTransport, policy: ExternalCallPolicy, asset_store: ContentAddressedAssetStore) -> None`**


### Functions


#### `_surface` `private`

```python
_surface(operation: ImageOperation) -> str
```

`imagine_client.py:57`


#### `_generated_images` `private`

```python
_generated_images(assets: tuple[StoredAsset, ...]) -> tuple[GeneratedImage, ...]
```

`imagine_client.py:61`


#### `_result_from_record` `private`

```python
_result_from_record(*, mode: ImagineMode, operation: ImageOperation, request: ImagineRequest, record: FixtureRecord) -> ImagineCallResult
```

`imagine_client.py:76`


Raises: `ImagineResponseError`


#### `build_imagine_client`

```python
build_imagine_client(*, mode: ImagineMode = ImagineMode.REPLAY, fixture_root: Path | str = 'fixtures/imagine_signal', transport: ImagineTransport | None = None, external_policy: ExternalCallPolicy | None = None, live_asset_store: ContentAddressedAssetStore | None = None) -> ImagineClient
```

`imagine_client.py:418`


Construct an explicitly configured client, defaulting to offline replay.


Raises: `ImagineConfigurationError`


---

## `outcomes.py`

Aggregate outcome snapshots and their idempotent repository. No raw user events anywhere.

> Aggregate outcome admission and deterministic signal estimation.


### Classes


#### `OutcomeErrorCode`

`outcomes.py:28` &nbsp;·&nbsp; bases: `StrEnum`


Stable failure codes surfaced by outcome admission and estimation.


| Field | Type | Default |
|---|---|---|
| `DUPLICATE_CONFLICT` | _(assigned)_ | `'IS5_DUPLICATE_CONFLICT'` |
| `TENANT_MISMATCH` | _(assigned)_ | `'IS5_TENANT_MISMATCH'` |
| `CAMPAIGN_MISMATCH` | _(assigned)_ | `'IS5_CAMPAIGN_MISMATCH'` |
| `CREATIVE_MISMATCH` | _(assigned)_ | `'IS5_CREATIVE_MISMATCH'` |
| `CONTEXT_MISMATCH` | _(assigned)_ | `'IS5_CONTEXT_MISMATCH'` |
| `EXPERIMENT_MISMATCH` | _(assigned)_ | `'IS5_EXPERIMENT_MISMATCH'` |
| `ARM_MISMATCH` | _(assigned)_ | `'IS5_ARM_MISMATCH'` |
| `WINDOW_MISMATCH` | _(assigned)_ | `'IS5_WINDOW_MISMATCH'` |
| `FUTURE_OBSERVATION` | _(assigned)_ | `'IS5_FUTURE_OBSERVATION'` |
| `STALE` | _(assigned)_ | `'IS5_OUTCOME_STALE'` |
| `PAIR_MISMATCH` | _(assigned)_ | `'IS6_OUTCOME_PAIR_MISMATCH'` |
| `ZERO_DENOMINATOR` | _(assigned)_ | `'IS6_ZERO_DENOMINATOR'` |
| `UNSUPPORTED_ORIGIN` | _(assigned)_ | `'IS6_UNSUPPORTED_ORIGIN'` |
| `FIXTURE_INVALID` | _(assigned)_ | `'IS5_FIXTURE_INVALID'` |



#### `OutcomeValidationError`

`outcomes.py:47` &nbsp;·&nbsp; bases: `ValueError`


Outcome failure carrying a stable machine-readable code.


- **`__init__(self, code: OutcomeErrorCode, detail: str) -> None`**


#### `AppendStatus`

`outcomes.py:56` &nbsp;·&nbsp; bases: `StrEnum`


| Field | Type | Default |
|---|---|---|
| `ACCEPTED` | _(assigned)_ | `'ACCEPTED'` |
| `DUPLICATE` | _(assigned)_ | `'DUPLICATE'` |



#### `AppendOutcomeResult`

`outcomes.py:62`


Result of an idempotent aggregate-snapshot append.


| Field | Type | Default |
|---|---|---|
| `status` | `AppendStatus` | - |
| `snapshot_hash` | `str` | - |



#### `OutcomeExpectation`

`outcomes.py:70`


Join and freshness constraints supplied by the campaign controller.


| Field | Type | Default |
|---|---|---|
| `tenant_id` | `str` | - |
| `campaign_id` | `str` | - |
| `creative_id` | `str` | - |
| `context_id` | `str` | - |
| `experiment_id` | `str` | - |
| `arm_id` | `str` | - |
| `measurement_window` | `MeasurementWindow` | - |
| `now` | `datetime` | - |
| `max_age` | `timedelta` | - |


- **`__post_init__(self) -> None`**
  <br/>Raises: `ValueError`


#### `FrozenOutcomeFixture`

`outcomes.py:91`


Verified, synthetic aggregate snapshots loaded from one committed file.


| Field | Type | Default |
|---|---|---|
| `description` | `str` | - |
| `snapshots` | `tuple[OutcomeSnapshot, ...]` | - |



#### `InMemoryOutcomeRepository`

`outcomes.py:98`


Thread-safe prototype repository with append-once snapshot identity.


- **`__init__(self) -> None`**

- **`append_once(self, snapshot: OutcomeSnapshot) -> AppendOutcomeResult`**
  <br/>Raises: `OutcomeValidationError`

- **`get(self, tenant_id: str, source_snapshot_id: str) -> OutcomeSnapshot | None`**

- **`snapshots(self, tenant_id: str) -> tuple[OutcomeSnapshot, ...]`**


### Functions


#### `load_frozen_outcome_fixture`

```python
load_frozen_outcome_fixture(path: Path | str) -> FrozenOutcomeFixture
```

`outcomes.py:137`


Load and verify the closed demo fixture shape and source payload digests.


Raises: `OutcomeValidationError`


#### `_snapshot_from_json_record` `private`

```python
_snapshot_from_json_record(value: object) -> OutcomeSnapshot
```

`outcomes.py:223`


Raises: `TypeError`


#### `validate_snapshot`

```python
validate_snapshot(snapshot: OutcomeSnapshot, expected: OutcomeExpectation) -> None
```

`outcomes.py:239`


Fail closed when a snapshot cannot join exactly to its declared arm.


Raises: `OutcomeValidationError`


#### `estimate_ctr_difference`

```python
estimate_ctr_difference(baseline: OutcomeSnapshot, variant: OutcomeSnapshot) -> SignalEstimate
```

`outcomes.py:295`


Compare aggregate CTR with a transparent paired-window approximation.


Raises: `OutcomeValidationError`


#### `_validate_estimation_pair` `private`

```python
_validate_estimation_pair(baseline: OutcomeSnapshot, variant: OutcomeSnapshot) -> None
```

`outcomes.py:346`


Raises: `OutcomeValidationError`


---

## `auction.py`

Auction sensitivity simulation. The largest module and the least defensible evidence: everything it produces is labeled SIMULATED.

> Deterministic auction sensitivity simulation for ImagineSignal.


### Classes


#### `AuctionMechanism`

`auction.py:28` &nbsp;·&nbsp; bases: `StrEnum`


Supported single-slot, pay-per-click pricing mechanisms.


| Field | Type | Default |
|---|---|---|
| `FIRST_PRICE` | _(assigned)_ | `'first_price'` |
| `SECOND_PRICE` | _(assigned)_ | `'second_price'` |
| `SOFT_FLOOR` | _(assigned)_ | `'soft_floor'` |



#### `LearningMode`

`auction.py:36` &nbsp;·&nbsp; bases: `StrEnum`


Bidder behavior modes, with adaptive modes restricted to research use.


| Field | Type | Default |
|---|---|---|
| `FIXED_BID` | _(assigned)_ | `'fixed_bid'` |
| `HEDGE_RESEARCH` | _(assigned)_ | `'hedge_research'` |
| `EXP3_IX_RESEARCH` | _(assigned)_ | `'exp3_ix_research'` |



#### `UtilityStatus`

`auction.py:44` &nbsp;·&nbsp; bases: `StrEnum`


Whether advertiser utility is identified by the supplied scenario.


| Field | Type | Default |
|---|---|---|
| `AVAILABLE` | _(assigned)_ | `'available'` |
| `UNAVAILABLE_MISSING_VALUES` | _(assigned)_ | `'unavailable_missing_values'` |



#### `QueryContext`

`auction.py:52`


A finite query or audience context and its arrival probability.


| Field | Type | Default |
|---|---|---|
| `context_id` | `str` | - |
| `probability` | `float` | - |


- **`__post_init__(self) -> None`**
  <br/>Raises: `ValueError`


#### `BidderContext`

`auction.py:66`


Bidder inputs for one context.


| Field | Type | Default |
|---|---|---|
| `context_id` | `str` | - |
| `predicted_ctr` | `float` | - |
| `true_ctr` | `float` | - |
| `value_per_click` | `float | None` | - |
| `eligible` | `bool` | `True` |


- **`__post_init__(self) -> None`**
  <br/>Raises: `ValueError`


#### `CreativeSignal`

`auction.py:91`


Replacement CTR signals for the focal creative in one context.


| Field | Type | Default |
|---|---|---|
| `context_id` | `str` | - |
| `predicted_ctr` | `float` | - |
| `true_ctr` | `float` | - |


- **`__post_init__(self) -> None`**


#### `BidderSpec`

`auction.py:105`


One bidder with a fixed target set and optional adaptive bid grid.


| Field | Type | Default |
|---|---|---|
| `bidder_id` | `str` | - |
| `fixed_bid` | `float` | - |
| `contexts` | `tuple[BidderContext, ...]` | - |
| `bid_grid` | `tuple[float, ...]` | `()` |


- **`__post_init__(self) -> None`**
  <br/>Raises: `ValueError`


#### `AuctionScenario`

`auction.py:133`


Fully disclosed single-slot auction sensitivity scenario.


| Field | Type | Default |
|---|---|---|
| `scenario_id` | `str` | - |
| `contexts` | `tuple[QueryContext, ...]` | - |
| `bidders` | `tuple[BidderSpec, ...]` | - |
| `focal_bidder_id` | `str` | - |
| `variant_signals` | `tuple[CreativeSignal, ...]` | - |
| `mechanism` | `AuctionMechanism` | `AuctionMechanism.FIRST_PRICE` |
| `learning_mode` | `LearningMode` | `LearningMode.FIXED_BID` |
| `soft_floor` | `float | None` | `None` |
| `horizon` | `int` | `10000` |
| `burn_in` | `int` | `0` |
| `seeds` | `tuple[int, ...]` | `(0,)` |
| `hedge_temperature` | `float` | `0.05` |
| `exp3_eta` | `float` | `0.05` |
| `exp3_gamma` | `float` | `0.01` |
| `stability_threshold` | `float` | `0.1` |
| `data_origin` | `str` | `'synthetic'` |
| `baseline_evidence_id` | `str | None` | `None` |
| `variant_evidence_id` | `str | None` | `None` |
| `assumptions` | `tuple[str, ...]` | `()` |
| `known_limitations` | `tuple[str, ...]` | `()` |


- **`__post_init__(self) -> None`**
  <br/>Raises: `ValueError`


#### `BidderUtility`

`auction.py:280`


| Field | Type | Default |
|---|---|---|
| `bidder_id` | `str` | - |
| `utility_per_impression` | `float` | - |



#### `AuctionRunSummary`

`auction.py:286`


Aggregate simulated outcomes for one creative world.


| Field | Type | Default |
|---|---|---|
| `simulated_seller_revenue_per_impression` | `float` | - |
| `simulated_advertiser_spend_per_impression` | `float` | - |
| `fill_rate` | `float` | - |
| `mean_eligible_bidders` | `float` | - |
| `participation_rate` | `float` | - |
| `winner_concentration_hhi` | `float | None` | - |
| `focal_advertiser_utility_per_impression` | `float | None` | - |
| `total_advertiser_utility_per_impression` | `float | None` | - |
| `bidder_utilities` | `tuple[BidderUtility, ...] | None` | - |
| `utility_status` | `UtilityStatus` | - |



#### `ScoreDistanceSummary`

`auction.py:302`


Distribution of focal score minus the highest eligible competitor score.


| Field | Type | Default |
|---|---|---|
| `count` | `int` | - |
| `mean` | `float | None` | - |
| `minimum` | `float | None` | - |
| `p10` | `float | None` | - |
| `median` | `float | None` | - |
| `p90` | `float | None` | - |
| `maximum` | `float | None` | - |



#### `SensitivityDelta`

`auction.py:315`


Paired variant-minus-baseline simulation deltas.


| Field | Type | Default |
|---|---|---|
| `simulated_seller_revenue_per_impression` | `float` | - |
| `simulated_advertiser_spend_per_impression` | `float` | - |
| `fill_rate` | `float` | - |
| `participation_rate` | `float` | - |
| `winner_concentration_hhi` | `float | None` | - |
| `focal_advertiser_utility_per_impression` | `float | None` | - |
| `total_advertiser_utility_per_impression` | `float | None` | - |
| `allocation_change_rate` | `float` | - |
| `focal_boundary_crossing_rate` | `float` | - |
| `mean_focal_score_distance` | `float | None` | - |



#### `ContextSensitivityResult`

`auction.py:331`


Paired metrics for one query context, or an explicit no-samples state.


| Field | Type | Default |
|---|---|---|
| `context_id` | `str` | - |
| `observations` | `int` | - |
| `status` | `str` | - |
| `baseline` | `AuctionRunSummary | None` | - |
| `variant` | `AuctionRunSummary | None` | - |
| `delta` | `SensitivityDelta | None` | - |
| `baseline_score_distance` | `ScoreDistanceSummary` | - |
| `variant_score_distance` | `ScoreDistanceSummary` | - |



#### `ConvergenceDiagnostics`

`auction.py:345`


Action-distribution stability over two halves of the evaluation window.


| Field | Type | Default |
|---|---|---|
| `status` | `str` | - |
| `converged` | `bool | None` | - |
| `max_total_variation` | `float | None` | - |
| `threshold` | `float` | - |
| `observations_per_half` | `int` | - |



#### `AuctionSensitivityResult`

`auction.py:356`


Receipt-like E2 auction sensitivity result.


| Field | Type | Default |
|---|---|---|
| `scenario_id` | `str` | - |
| `scenario_hash` | `str` | - |
| `code_version` | `str` | - |
| `evidence_class` | `str` | - |
| `data_origin` | `str` | - |
| `mechanism` | `AuctionMechanism` | - |
| `learning_mode` | `LearningMode` | - |
| `seeds` | `tuple[int, ...]` | - |
| `repetitions` | `int` | - |
| `horizon` | `int` | - |
| `burn_in` | `int` | - |
| `common_randomness_id` | `str` | - |
| `baseline_evidence_hash` | `str` | - |
| `variant_evidence_hash` | `str` | - |
| `baseline` | `AuctionRunSummary` | - |
| `variant` | `AuctionRunSummary` | - |
| `delta` | `SensitivityDelta` | - |
| `baseline_score_distance` | `ScoreDistanceSummary` | - |
| `variant_score_distance` | `ScoreDistanceSummary` | - |
| `context_results` | `tuple[ContextSensitivityResult, ...]` | - |
| `revenue_delta_standard_error` | `float | None` | - |
| `baseline_convergence` | `ConvergenceDiagnostics` | - |
| `variant_convergence` | `ConvergenceDiagnostics` | - |
| `assumptions` | `tuple[str, ...]` | - |
| `known_limitations` | `tuple[str, ...]` | - |
| `allowed_claim` | `str` | - |
| `disallowed_claims` | `tuple[str, ...]` | - |


- **`to_dict(self) -> dict[str, Any]`**
  <br/>Return a stable JSON-compatible representation.
  <br/>Raises: `TypeError`


#### `AdaptiveRobustnessResult`

`auction.py:397`


Mandatory paired report for Hedge and EXP3-IX research simulations.


| Field | Type | Default |
|---|---|---|
| `scenario_id` | `str` | - |
| `scenario_family_hash` | `str` | - |
| `evidence_class` | `str` | - |
| `hedge` | `AuctionSensitivityResult` | - |
| `exp3_ix` | `AuctionSensitivityResult` | - |
| `revenue_delta_sign_agreement` | `bool` | - |
| `all_runs_stable` | `bool` | - |
| `status` | `str` | - |
| `allowed_claim` | `str` | - |
| `disallowed_claims` | `tuple[str, ...]` | - |


- **`to_dict(self) -> dict[str, Any]`**
  <br/>Return a stable JSON-compatible representation.
  <br/>Raises: `TypeError`


#### `_AuctionOutcome` `private`

`auction.py:421`


| Field | Type | Default |
|---|---|---|
| `context_id` | `str` | - |
| `winner_id` | `str | None` | - |
| `price_per_click` | `float` | - |
| `revenue` | `float` | - |
| `participant_count` | `int` | - |
| `utilities` | `tuple[tuple[str, float], ...] | None` | - |
| `focal_margin` | `float | None` | - |



#### `_WorldTrace` `private`

`auction.py:432`


| Field | Type | Default |
|---|---|---|
| `outcomes` | `tuple[_AuctionOutcome, ...]` | - |
| `action_indices` | `tuple[tuple[int, ...], ...]` | - |



### Functions


#### `run_auction_sensitivity`

```python
run_auction_sensitivity(scenario: AuctionScenario) -> AuctionSensitivityResult
```

`auction.py:437`


Run paired baseline and focal-variant auction simulations.


#### `run_adaptive_robustness`

```python
run_adaptive_robustness(scenario: AuctionScenario) -> AdaptiveRobustnessResult
```

`auction.py:583`


Run Hedge and EXP3-IX together so neither learner can be cherry-picked.


Raises: `TypeError`


#### `stable_hash`

```python
stable_hash(value: Any) -> str
```

`auction.py:636`


Hash a value after deterministic JSON normalization.


#### `_validate_runtime_requirements` `private`

```python
_validate_runtime_requirements(scenario: AuctionScenario) -> None
```

`auction.py:642`


Raises: `ValueError`


#### `_simulate_world` `private`

```python
_simulate_world(scenario: AuctionScenario, *, seed: int, use_variant: bool) -> _WorldTrace
```

`auction.py:662`


#### `_run_single_auction` `private`

```python
_run_single_auction(scenario: AuctionScenario, *, context_id: str, bids: dict[str, float], priorities: dict[str, float], use_variant: bool) -> _AuctionOutcome
```

`auction.py:756`


Raises: `ValueError`


#### `_normalized_reward` `private`

```python
_normalized_reward(scenario: AuctionScenario, bidder: BidderSpec, outcome: _AuctionOutcome, action_values: tuple[float, ...]) -> float
```

`auction.py:872`


Raises: `ValueError`


#### `_action_probabilities` `private`

```python
_action_probabilities(state: list[float], mode: LearningMode, *, hedge_temperature: float, exp3_eta: float) -> tuple[float, ...]
```

`auction.py:890`


#### `_softmax` `private`

```python
_softmax(logits: tuple[float, ...]) -> tuple[float, ...]
```

`auction.py:906`


#### `_sample_context` `private`

```python
_sample_context(contexts: tuple[QueryContext, ...], draw: float) -> str
```

`auction.py:913`


#### `_sample_index` `private`

```python
_sample_index(probabilities: tuple[float, ...], draw: float) -> int
```

`auction.py:922`


#### `_summarize_world` `private`

```python
_summarize_world(scenario: AuctionScenario, outcomes: tuple[_AuctionOutcome, ...]) -> AuctionRunSummary
```

`auction.py:931`


#### `_build_delta` `private`

```python
_build_delta(scenario: AuctionScenario, baseline_outcomes: tuple[_AuctionOutcome, ...], variant_outcomes: tuple[_AuctionOutcome, ...], baseline_summary: AuctionRunSummary, variant_summary: AuctionRunSummary, baseline_distance: ScoreDistanceSummary, variant_distance: ScoreDistanceSummary) -> SensitivityDelta
```

`auction.py:985`


Raises: `ValueError`


#### `_summarize_contexts` `private`

```python
_summarize_contexts(scenario: AuctionScenario, baseline_outcomes: tuple[_AuctionOutcome, ...], variant_outcomes: tuple[_AuctionOutcome, ...]) -> tuple[ContextSensitivityResult, ...]
```

`auction.py:1046`


Raises: `ValueError`


#### `_summarize_distances` `private`

```python
_summarize_distances(values: tuple[float, ...]) -> ScoreDistanceSummary
```

`auction.py:1108`


#### `_quantile` `private`

```python
_quantile(ordered: tuple[float, ...], probability: float) -> float
```

`auction.py:1123`


#### `_convergence_diagnostics` `private`

```python
_convergence_diagnostics(scenario: AuctionScenario, traces: list[_WorldTrace]) -> ConvergenceDiagnostics
```

`auction.py:1133`


#### `_utility_status` `private`

```python
_utility_status(scenario: AuctionScenario) -> UtilityStatus
```

`auction.py:1186`


#### `_zero_utilities_if_available` `private`

```python
_zero_utilities_if_available(scenario: AuctionScenario) -> tuple[tuple[str, float], ...] | None
```

`auction.py:1196`


#### `_signal_hash` `private`

```python
_signal_hash(scenario: AuctionScenario, *, use_variant: bool) -> str
```

`auction.py:1204`


#### `_standard_error` `private`

```python
_standard_error(values: list[float]) -> float | None
```

`auction.py:1228`


#### `_optional_delta` `private`

```python
_optional_delta(left: float | None, right: float | None) -> float | None
```

`auction.py:1234`


#### `_sign` `private`

```python
_sign(value: float, *, tolerance: float = 1e-12) -> int
```

`auction.py:1240`


#### `_mean` `private`

```python
_mean(values: Any) -> float
```

`auction.py:1248`


#### `_to_primitive` `private`

```python
_to_primitive(value: Any) -> Any
```

`auction.py:1253`


#### `_require_nonempty` `private`

```python
_require_nonempty(value: str, field_name: str) -> None
```

`auction.py:1267`


Raises: `ValueError`


#### `_normalized_nonempty` `private`

```python
_normalized_nonempty(value: str, field_name: str) -> str
```

`auction.py:1272`


#### `_require_finite` `private`

```python
_require_finite(value: float, field_name: str) -> None
```

`auction.py:1277`


Raises: `ValueError`


#### `_require_nonnegative` `private`

```python
_require_nonnegative(value: float, field_name: str) -> None
```

`auction.py:1284`


Raises: `ValueError`


#### `_require_positive` `private`

```python
_require_positive(value: float, field_name: str) -> None
```

`auction.py:1290`


Raises: `ValueError`


#### `_require_probability` `private`

```python
_require_probability(value: float, field_name: str) -> None
```

`auction.py:1296`


Raises: `ValueError`


#### `_require_unique` `private`

```python
_require_unique(values: Any, field_name: str) -> None
```

`auction.py:1302`


Raises: `ValueError`


---

## `gates.py`

`IS0` through `IS8` as pure functions. A wrong gate invalidates every claim the system makes, which is why this file is held at 100 percent line and branch.

> Pure IS0 through IS8 gates for creative lineage and evidence admission.


### Functions


#### `_ok` `private`

```python
_ok(gate: str, schema_version: str) -> SignalGateResult
```

`gates.py:29`


#### `_fail` `private`

```python
_fail(gate: str, code: str, detail: str, coerce_to: NextAction, schema_version: str, *, security_signal: bool = False) -> SignalGateResult
```

`gates.py:38`


#### `is0_request_budget`

```python
is0_request_budget(*, mode: DeploymentMode, allowed_modes: frozenset[DeploymentMode], requested_calls: int, requested_images: int, requested_quality_images: int, requested_cost_in_usd_ticks: int | None, cost_status: CostStatus, elapsed_ms: int, budget: GenerationBudget, generation_enabled: bool, schema_version: str) -> SignalGateResult
```

`gates.py:58`


Admit only an explicit mode and work request bounded in every dimension.


#### `is1_lineage`

```python
is1_lineage(*, campaign: CampaignSpec, child: CreativeAsset, parent: CreativeAsset | None, schema_version: str) -> SignalGateResult
```

`gates.py:141`


Validate campaign, tenant, parent, and root lineage.


#### `is2_controlled_mutation`

```python
is2_controlled_mutation(mutations: Sequence[MutationSpec], *, observed_changes: Mapping[str, Collection[str]] | None, observed_locked_hashes: Mapping[str, Mapping[str, str]] | None, schema_version: str) -> SignalGateResult
```

`gates.py:223`


Admit only a coherent family whose outputs changed one declared atom.


#### `is3_provider_admission`

```python
is3_provider_admission(asset: CreativeAsset, *, provider_completed: bool, schema_version: str) -> SignalGateResult
```

`gates.py:248`


Reject ambiguous completion, moderation bypass, and unknown paid cost.


#### `is4_asset_integrity`

```python
is4_asset_integrity(asset: CreativeAsset, *, computed_media_sha256: str, actual_width: int, actual_height: int, duplicate_of: str | None, schema_version: str) -> SignalGateResult
```

`gates.py:301`


Admit only persisted bytes with the declared digest and dimensions.


#### `is5_outcome_admission`

```python
is5_outcome_admission(snapshot: OutcomeSnapshot, *, campaign: CampaignSpec, asset: CreativeAsset, now: datetime, max_staleness: timedelta, expected_experiment_id: str, expected_arm_id: str, complete: bool, schema_version: str) -> SignalGateResult
```

`gates.py:369`


Validate aggregate outcome identity, window, freshness, and completeness.


#### `is6_statistical_validity`

```python
is6_statistical_validity(estimate: SignalEstimate, *, min_sample_size: int, require_interval_excludes_zero: bool, schema_version: str) -> SignalGateResult
```

`gates.py:461`


Validate metric namespace, sample size, and optional interval criterion.


#### `_sign` `private`

```python
_sign(value: float, tolerance: float = 1e-12) -> int
```

`gates.py:507`


#### `is7_auction_sensitivity`

```python
is7_auction_sensitivity(results: Sequence[AuctionSensitivityRecord], *, require_adaptive_pair: bool, schema_version: str) -> SignalGateResult
```

`gates.py:515`


Require paired, converged, non-cherry-picked sensitivity evidence.


#### `is8_evidence_action`

```python
is8_evidence_action(*, evidence_class: EvidenceClass, proposed_action: NextAction, mode: DeploymentMode, schema_version: str) -> SignalGateResult
```

`gates.py:583`


Enforce the total evidence-to-action ceiling.


---

## `decisions.py`

The evidence-to-action ceiling and deterministic action resolution.

> Evidence ceilings and deterministic action resolution for ImagineSignal.


### Functions


#### `allowed_actions`

```python
allowed_actions(evidence_class: EvidenceClass, mode: DeploymentMode) -> frozenset[NextAction]
```

`decisions.py:44`


Return the complete action set admitted by evidence and environment.


#### `evidence_capped_action`

```python
evidence_capped_action(proposed_action: NextAction, evidence_class: EvidenceClass, mode: DeploymentMode) -> NextAction
```

`decisions.py:62`


Return the proposal when allowed, otherwise fail closed to HOLD.


#### `resolve_final_action`

```python
resolve_final_action(proposed_action: NextAction, gate_results: Sequence[SignalGateResult]) -> NextAction
```

`decisions.py:74`


Combine gate coercions without consulting rationale or free-form text.


#### `default_claim_wording`

```python
default_claim_wording(evidence_class: EvidenceClass) -> str
```

`decisions.py:87`


Return conservative wording tied to the evidence provenance.


#### `build_signal_decision`

```python
build_signal_decision(*, schema_version: str, evidence_class: EvidenceClass, proposed_action: NextAction, mode: DeploymentMode, gate_results: Sequence[SignalGateResult], claim_wording: str | None = None, rationale: str = '') -> SignalDecision
```

`decisions.py:123`


Build a decision with one authoritative IS8 result and a deterministic final action.


Raises: `ValueError`


---

## `receipts.py`

Append-once, digest-linked decision receipts with tamper detection.

> Immutable, digest-linked decision receipt construction and verification.


### Functions


#### `_sorted_unique` `private`

```python
_sorted_unique(values: Sequence[str], field_name: str) -> tuple[str, ...]
```

`receipts.py:17`


Raises: `ValueError`


#### `build_decision_receipt`

```python
build_decision_receipt(*, schema_version: str, receipt_id: str, receipt_version: int, tenant_id: str, campaign_hash: str, family_hash: str, asset_hashes: Sequence[str], outcome_hashes: Sequence[str], scenario_hashes: Sequence[str], decision: SignalDecision, human_approval: HumanApproval | None, cost_total_ticks: int | None, cost_status: CostStatus, trace_id: str, created_at: datetime, previous_receipt_sha256: str | None = None) -> DecisionReceipt
```

`receipts.py:24`


Build and sign a complete receipt from immutable source digests.


Raises: `ValueError`


#### `verify_receipt`

```python
verify_receipt(receipt: DecisionReceipt) -> bool
```

`receipts.py:78`


Recompute a receipt digest, including for unvalidated model copies.


#### `revise_receipt`

```python
revise_receipt(previous: DecisionReceipt, *, decision: SignalDecision, approval: HumanApproval, created_at: datetime) -> DecisionReceipt
```

`receipts.py:85`


Append one immutable revision linked to the exact previous receipt.


Raises: `ValueError`


#### `receipt_json`

```python
receipt_json(receipt: DecisionReceipt) -> str
```

`receipts.py:118`


Return canonical export JSON after verifying its digest.


Raises: `ValueError`


---

## `service.py`

The offline orchestrator. Idempotent per key and semantic request hash.

> Credential-free end-to-end orchestration for the ImagineSignal offline MVP.


### Classes


#### `OfflineServiceError`

`service.py:76` &nbsp;·&nbsp; bases: `RuntimeError`


Fail-closed orchestration error with a stable local code.


- **`__init__(self, code: str, detail: str) -> None`**


#### `PlannedCreative`

`service.py:86`


One replay request bound to its intended lineage identity.


| Field | Type | Default |
|---|---|---|
| `creative_id` | `str` | - |
| `root_creative_id` | `str` | - |
| `parent_creative_id` | `str | None` | - |
| `mutation_id` | `str | None` | - |
| `request` | `ImageGenerationRequest` | - |



#### `EfficiencyInput`

`service.py:97`


Frozen counts for one same-output-budget workflow.


| Field | Type | Default |
|---|---|---|
| `generated_count` | `int` | - |
| `qualified_count` | `int` | - |
| `duplicate_paid_outputs` | `int` | - |
| `quality_outputs` | `int` | - |
| `qualified_quality_outputs` | `int` | - |
| `lineage_complete_count` | `int` | - |
| `total_cost_ticks` | `int` | - |


- **`__post_init__(self) -> None`**
  <br/>Raises: `ValueError`


#### `EfficiencyMetrics`

`service.py:133`


Recomputable workflow-efficiency metrics with unavailable denominators.


| Field | Type | Default |
|---|---|---|
| `generated_count` | `int` | - |
| `qualified_count` | `int` | - |
| `duplicate_paid_outputs` | `int` | - |
| `total_cost_ticks` | `int` | - |
| `qualified_creative_yield` | `float | None` | - |
| `cost_per_qualified_creative_ticks` | `float | None` | - |
| `duplicate_paid_output_rate` | `float | None` | - |
| `quality_precision` | `float | None` | - |
| `lineage_completeness` | `float | None` | - |



#### `SameBudgetEfficiency`

`service.py:148`


Controlled workflow and an explicitly synthetic equal-budget baseline.


| Field | Type | Default |
|---|---|---|
| `evidence_class` | `str` | - |
| `cost_basis` | `str` | - |
| `controlled` | `EfficiencyMetrics` | - |
| `unstructured_baseline` | `EfficiencyMetrics` | - |



#### `OfflineFamilyRequest`

`service.py:158`


Complete immutable input to one credential-free family evaluation.


| Field | Type | Default |
|---|---|---|
| `idempotency_key` | `str` | - |
| `tenant_id` | `str` | - |
| `expected_campaign_hash` | `str` | - |
| `campaign` | `CampaignSpec` | - |
| `brand` | `BrandSpec` | - |
| `mutations` | `tuple[MutationSpec, ...]` | - |
| `planned_creatives` | `tuple[PlannedCreative, ...]` | - |
| `evaluation_control_creative_id` | `str` | - |
| `evaluation_variant_creative_id` | `str` | - |
| `expected_experiment_id` | `str` | - |
| `arm_assignments` | `tuple[tuple[str, str], ...]` | - |
| `observed_changes` | `tuple[tuple[str, tuple[str, ...]], ...]` | - |
| `observed_locked_hashes` | `tuple[tuple[str, tuple[tuple[str, str], ...]], ...]` | - |
| `outcome_fixture_path` | `str` | - |
| `auction_scenario` | `AuctionScenario` | - |
| `baseline_efficiency` | `EfficiencyInput` | - |
| `proposed_action` | `NextAction` | - |
| `now` | `datetime` | - |
| `max_outcome_staleness` | `timedelta` | - |
| `min_sample_size` | `int` | - |
| `trace_id` | `str` | - |
| `created_at` | `datetime` | - |


- **`__post_init__(self) -> None`**
  <br/>Raises: `ValueError`


#### `OfflineRunResult`

`service.py:204`


Artifact-ready result of one complete replay evaluation.


| Field | Type | Default |
|---|---|---|
| `request_hash` | `str` | - |
| `assets` | `tuple[CreativeAsset, ...]` | - |
| `signal_estimates` | `tuple[SignalEstimate, ...]` | - |
| `auction_result` | `AuctionSensitivityResult` | - |
| `auction_record` | `AuctionSensitivityRecord` | - |
| `efficiency` | `SameBudgetEfficiency` | - |
| `decision` | `SignalDecision` | - |
| `receipt` | `DecisionReceipt` | - |
| `explanation` | `str` | - |


- **`to_dict(self) -> dict[str, object]`**


#### `InMemoryReceiptLedger`

`service.py:253`


Append-once local ledger used only by the offline service.


- **`__init__(self) -> None`**

- **`append_once(self, receipt: DecisionReceipt) -> DecisionReceipt`**
  <br/>Raises: `OfflineServiceError`

- **`get(self, receipt_id: str) -> DecisionReceipt | None`**


#### `OfflineImagineSignalService`

`service.py:278`


Idempotent fixture-only orchestrator with no live or write adapter.


- **`__init__(self, client: FixtureImagineClient, *, outcome_repository: InMemoryOutcomeRepository | None = None, receipt_ledger: InMemoryReceiptLedger | None = None) -> None`**
  <br/>Raises: `OfflineServiceError`

- **`run(self, request: OfflineFamilyRequest) -> OfflineRunResult`**
  <br/>Execute exactly once per idempotency key and semantic request hash.
  <br/>Raises: `OfflineServiceError`

- **`_execute(self, request: OfflineFamilyRequest, request_hash: str, snapshots) -> OfflineRunResult`**

- **`_replay_assets(self, request: OfflineFamilyRequest) -> tuple[tuple[CreativeAsset, ...], dict[str, tuple[SignalGateResult, ...]], int]`**
  <br/>Raises: `OfflineServiceError`


### Functions


#### `_validate_request_contracts` `private`

```python
_validate_request_contracts(request: OfflineFamilyRequest) -> None
```

`service.py:566`


Raises: `OfflineServiceError`


#### `_estimate_contexts` `private`

```python
_estimate_contexts(snapshots, *, control_creative_id: str, variant_creative_id: str) -> tuple[SignalEstimate, ...]
```

`service.py:653`


Raises: `OfflineServiceError`


#### `_auction_record` `private`

```python
_auction_record(result: AuctionSensitivityResult) -> AuctionSensitivityRecord
```

`service.py:683`


Raises: `OfflineServiceError`


#### `_same_budget_efficiency` `private`

```python
_same_budget_efficiency(assets: tuple[CreativeAsset, ...], *, gate_groups: dict[str, tuple[SignalGateResult, ...]], baseline: EfficiencyInput, total_cost_ticks: int) -> SameBudgetEfficiency
```

`service.py:753`


Raises: `OfflineServiceError`


#### `_efficiency_metrics` `private`

```python
_efficiency_metrics(value: EfficiencyInput) -> EfficiencyMetrics
```

`service.py:797`


#### `_safe_ratio` `private`

```python
_safe_ratio(numerator: int, denominator: int) -> float | None
```

`service.py:813`


#### `_efficiency_dict` `private`

```python
_efficiency_dict(value: EfficiencyMetrics) -> dict[str, object]
```

`service.py:817`


#### `_aggregate_gate` `private`

```python
_aggregate_gate(results: tuple[SignalGateResult, ...]) -> SignalGateResult
```

`service.py:831`


Raises: `OfflineServiceError`


#### `_required_asset` `private`

```python
_required_asset(assets: dict[str, CreativeAsset], creative_id: str) -> CreativeAsset
```

`service.py:848`


Raises: `OfflineServiceError`


#### `_required_arm` `private`

```python
_required_arm(assignments: dict[str, str], creative_id: str) -> str
```

`service.py:858`


Raises: `OfflineServiceError`


#### `_offline_request_hash` `private`

```python
_offline_request_hash(request: OfflineFamilyRequest, snapshots) -> str
```

`service.py:868`


---

## `demo.py`

Deterministic artifact generation for the reviewed offline demo.

> Frozen construction inputs for the credential-free ImagineSignal demo.


### Functions


#### `_generation_request` `private`

```python
_generation_request(prompt: str) -> ImageGenerationRequest
```

`demo.py:51`


#### `build_demo_request`

```python
build_demo_request(repo_root: Path | str | None = None) -> OfflineFamilyRequest
```

`demo.py:63`


Build the exact request matched by committed synthetic replay fixtures.


---

## `__init__.py`

Public package surface.

> ImagineSignal controlled creative learning package.

_Re-exports only. See the package `__all__`._
