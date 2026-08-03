# Adjacency Architecture

## Part 1: Theory and problem

Adjacency applies the same discipline as Spatial Atlas to a different high-stakes surface. Spatial Atlas turns uncertain perception into typed scene state, computes over that state, and keeps uncertain execution behind gates. Adjacency turns advertiser prose into typed policy state, judges multimodal inventory, and keeps uncertain delivery behind deterministic admission.

The central separation is:

- Models extract and propose.
- Frozen contracts define what a proposal must contain.
- Deterministic code verifies whether the proposal is admissible.
- The delivery disposition changes only after verification.
- Failed verification has a destination: `REVIEW` and an auditable human queue.

This structure matters because brand-safety failure has two directions. `UNDER_BLOCK` exposes an advertiser to risk that a lexical baseline cannot see. `OVER_BLOCK` withholds safe inventory because a term match cannot express context. `src/adjacency/delta.py` defines those dispositions without asking a model to compare its own work.

## Part 2: File interaction map

```text
Advertiser prose
      |
      +--> policy.py --> contracts.py: PolicySpec
      |        |
      |        +--> gates.py: G0 source-span admission
      |
      +--> baseline.py: KeywordExpander --> BaselineBlocklist
                                      |
Frozen inventory                      |
      |                               |
      +--> corpus.py -----------------+
      |                               |
      +--> tier_zero.py               |
      |        |                      |
      |        +--> deterministic decision when admissible
      |        |
      |        +--> judge.py: Tier 1 or Tier 2 structured verdict
      |                          |
      |                          +--> gates.py: G1 through G6
      |                                      |
      |                                      +--> accepted disposition
      |                                      +--> forced REVIEW
      |
      +--> baseline.py: BaselineMatcher
                  |                 |
                  +------ delta.py -+
                              |
                              +--> AGREE
                              +--> OVER_BLOCK
                              +--> UNDER_BLOCK
                                      |
                                      +--> autopsy.py --> ui.py --> app.py
                                      |
                                      +--> hitl.py: in-process queue
                                                   |
                                                   +--> temporal_hitl.py
                                                        opt-in adapter only

External-call boundary
      |
      +--> xai.py --> fixtures.py: record once, replay by default
      +--> inventory.py: x_search discovery plus direct-status verification
      +--> sources.py: fixed source selection and evaluation-source guard
```

## Part 3: File-by-file walkthrough

### `src/adjacency/contracts.py`: frozen state

This module defines the immutable vocabulary shared across the engine. `PolicySpec` contains normalized advertiser prose, grounded clauses, a version, and a stable content hash. `InventoryItem` carries text and media metadata. `Verdict` carries structured action, severity, cited policy clauses, and evidence. `DeltaRow` stores the engine-versus-baseline result.

Text evidence uses character offsets into NFC-normalized strings. The quote remains the source of truth. An offset is a claim that G1 must reproduce rather than a value the system trusts.

### `src/adjacency/policy.py`: policy compiler

`PolicyCompiler` sends trusted advertiser prose through a recorded structured-output call. It parses only the typed response. Before returning a policy, it executes G0 from `src/adjacency/gates.py`. Every clause quote must equal the normalized source slice at the declared offsets. A failed clause prevents compilation.

The compiled demonstration policy is stored in `artifacts/tuesday/policy_spec.json`. Its hash is carried into the blocklist and later evaluation artifacts so comparisons cannot silently cross policy versions.

### `src/adjacency/baseline.py`: same-prose lexical control

`KeywordExpander` receives the identical advertiser prose and returns normalized terms. `BaselineBlocklist` stores the source prose and source policy hash beside those terms. `BaselineMatcher` is deterministic. It records matched terms and produces the lexical delivery decision used by the delta engine.

The generated control is `artifacts/tuesday/baseline_blocklist.json`. It is a project baseline, not a representation of X's private implementation.

### `src/adjacency/inventory.py` and `src/adjacency/corpus.py`: verified inventory

`InventoryFetcher` discovers candidate posts through recorded `x_search` calls. `XStatusResolver` checks canonical direct-status sources before an item can enter the corpus. `CorpusFreezer` normalizes downloaded images, records media digests, and writes a stable corpus hash.

`corpus/frozen/manifest.json` is the authority for the frozen evaluation set and local media integrity. `src/adjacency/sources.py` prevents evaluation from drifting to a live source.

### `src/adjacency/tier_zero.py` and `src/adjacency/judge.py`: selective reasoning

`decide_tier_zero` handles admissible clean-text cases without a model call. `AdjacencyJudge` sends residual items to low reasoning, then escalates when explicit predicates require stronger reasoning. Escalation causes include missing media analysis, low confidence, abstention, gate failure, model-call failure, and near-duplicate disagreement.

The judge does not get the final word. Every structured verdict passes `run_verdict_gates`. Routing and per-call measurements are stored in `artifacts/wednesday/judge_report.json` and `artifacts/wednesday/judge_traces.json`.

### `src/adjacency/gates.py`: deterministic admission

The gate chain covers compile-time source grounding and per-verdict evidence, policy, monotonicity, severity, budget, and abstention checks. Each result is a typed `GateResult` with a stable code. `GateChainResult` carries both the proposed and final dispositions.

`G1_SPAN_NOT_FOUND` is the visual proof of the architecture. A fluent rationale cannot repair an invalid evidence offset. The deterministic layer changes the proposed `ALLOW` to `REVIEW` and records the reason.

### `src/adjacency/delta.py`, `src/adjacency/autopsy.py`, and `src/adjacency/ui.py`: comparison and inspection

`DeltaEngine` compares the admitted engine action with the baseline action. `load_autopsy_bundle` validates the frozen traces, policy hash, corpus hash, media files, and illustrative economics input before creating the UI model. `AutopsyDemo` emits deterministic frames. The Gradio layer renders the frame without making a network call.

The UI starts in `demo` mode and rejects unsupported modes in `src/adjacency/ui.py`. `app.py` is only a thin launch wrapper.

### `src/adjacency/hitl.py` and `src/adjacency/temporal_hitl.py`: review destination

`HITLQueue` is a small protocol. `InProcessHITLQueue` is the default implementation and the only implementation used by the demo. `create_hitl_queue` imports the Temporal adapter only after `ADJ_HITL_BACKEND=temporal` is explicitly selected.

The optional adapter contains one workflow, one human-adjudication signal, and one queue-state query. The live protocol evidence is `artifacts/temporal/hitl_live_proof.json`. Temporal does not own judging, gates, corpus state, or UI state.

### `src/adjacency/fixtures.py` and `src/adjacency/xai.py`: reproducible model boundary

`RecordedXAIClient` replays by default. `FixtureStore` hashes canonical requests, verifies response integrity, and rejects secret-shaped data before recording. A live request requires both credentials and `ADJ_RECORD=1`.

This boundary gives the project a useful split. Live calls prove the provider surfaces. Frozen replay proves that local tests, artifacts, the paper, the deck, and the demo do not depend on provider availability.

## Part 4: End-to-end flows

### Policy compilation flow

1. Normalize trusted advertiser prose in `src/adjacency/contracts.py`.
2. Request a structured clause set through `src/adjacency/policy.py`.
3. Validate the typed response.
4. Recompute every source slice with G0 in `src/adjacency/gates.py`.
5. Freeze the admitted `PolicySpec` and its content hash.
6. Generate `BaselineBlocklist` from the same normalized prose.

### Frozen evaluation flow

1. Load and verify `corpus/frozen/manifest.json` through `src/adjacency/corpus.py`.
2. Attempt the deterministic Tier 0 decision in `src/adjacency/tier_zero.py`.
3. Route unresolved inventory through the judge ladder in `src/adjacency/judge.py`.
4. Recompute applicable gates in `src/adjacency/gates.py`.
5. Replace inadmissible serving dispositions with `REVIEW`.
6. Compare the final engine action with `BaselineMatcher` through `src/adjacency/delta.py`.
7. Write stable traces and aggregate measurements under `artifacts/wednesday/`.

### Autopsy flow

1. Load the committed policy, blocklist, traces, corpus, and economics assumption in `src/adjacency/autopsy.py`.
2. Reject a mismatched hash, missing media file, or malformed trace before UI construction.
3. Stream deterministic frames into the `AGREE`, `OVER_BLOCK`, and `UNDER_BLOCK` columns.
4. Select a row to render its evidence, cited image region, gate chain, and audit payload.
5. Route `REVIEW` records into the default in-process queue.

### Optional durable-review flow

1. An operator selects `ADJ_HITL_BACKEND=temporal` outside the demo.
2. `create_hitl_queue` imports and connects the adapter.
3. A review request starts `AdjacencyHITLReview`.
4. A human adjudication arrives through the `adjudicate` signal.
5. `queue_state` exposes the durable state without mutating it.
6. The workflow completes with the adjudicated review state.

## Part 5: Key design decisions

### Typed output is necessary but insufficient

A valid schema can still contain a fabricated quote, a wrong offset, a stale clause identifier, or an incoherent severity. The schema makes those claims inspectable. The gates decide whether they are true.

### Rationale is display-only

The final disposition comes from structured fields and deterministic checks. The rationale can explain the result to a person. It cannot override a gate.

### The baseline receives the same prose

The comparison changes representation, not policy intent. Carrying the source policy hash into `artifacts/tuesday/baseline_blocklist.json` keeps that constraint auditable.

### Failure is a product state

Uncertainty does not disappear into a log. It produces `REVIEW`, retains its audit chain, and enters a queue with a defined adjudication contract.

### Durable infrastructure remains replaceable

The review protocol lives in `src/adjacency/hitl.py`. Temporal is one opt-in adapter behind that protocol. The demo and deterministic engine remain operational when the service is unavailable.

### Evaluation is frozen before presentation

The paper, deck, results sheet, and UI all name committed artifacts. Live calls can be re-recorded intentionally, but a presentation cannot silently change because a hosted model or public post changed.
