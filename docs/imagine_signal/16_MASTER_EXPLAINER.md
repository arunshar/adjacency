# ImagineSignal master explainer

| Field | Value |
|---|---|
| Version | 1.0 |
| Written | 2026-08-05 |
| Repository | `/Users/arunsharma/code/adjacency`, `main` at `cd218dd`, intentionally dirty |
| Verified state | 448 passed, 2 xfailed (see section 8 for why the count moves) |
| Product status | Offline MVP complete, production NO_GO, action ceiling TEST |

This is the single document that explains the whole project. It links out rather than restating:
the [PRD](02_PRD.md), [system design](03_SYSTEM_DESIGN.md), and
[technical spec](04_TECHNICAL_SPEC.md) remain authoritative for their own areas, and the
[complete API reference](17_API_REFERENCE.md) carries all 304 symbols.

Diagrams live in [`diagrams/`](diagrams/) and are also editable as Excalidraw scenes in the
`arunshar` workspace. The rendered walkthrough is [`system_design.html`](system_design.html).

---

## 1. The product in plain language

An advertiser has one approved ad image. The obvious thing to do with a generative model is make
fifty more. The problem is that you then have fifty images and no idea which difference mattered,
what it cost, or whether you are allowed to say anything about it.

ImagineSignal makes a small family instead. Exactly one declared visual choice changes at a time.
Product, logo, composition, and text stay locked and are verified to be byte-identical. The system
records creative lineage and the actual cost of every generation, joins clearly labeled outcome
evidence, estimates whether a response difference deserves more testing, and simulates whether that
small signal could matter near an ad-selection boundary.

The output is not an image. It is a **decision receipt**: keep, edit, test, hold, review, or stop,
with the evidence class that justified it attached and a digest chain that makes tampering
detectable.

The interesting engineering is not the generation. It is that the system refuses to claim more than
its evidence supports, and that the refusal is enforced in code rather than in a style guide.

### The failure mode it targets

| What generative ad tooling does | What it cannot then answer |
|---|---|
| Generate many variants at once | Which visual factor caused the difference |
| Keep the best-looking output | Whether "best-looking" survives a real test |
| Report generation count and latency | Cost per output that was actually usable |
| Show a quality score | Whether the claim is causal or decorative |

## 2. How this relates to base Adjacency

Base Adjacency is a brand-safety policy engine. It compiles advertiser prose into a typed, hashed,
diffable `PolicySpec`, evaluates inventory, and reports the delta against a keyword blocklist split
into under-blocks and over-blocks. Its gates are `G0` through `G6`.

ImagineSignal extends the same discipline to the creative side, and it is **deliberately isolated**:

- All new code lives under `src/adjacency/imagine_signal/`.
- Its gates are `IS0` through `IS8`, a separate namespace from `G0` through `G6`.
- It has its own canonical hashing (`canonical.py`) rather than importing the private helper from
  base Adjacency, so ImagineSignal contracts can evolve without moving existing hash vectors.
- Nothing in base Adjacency imports ImagineSignal.

The isolation is the point. The frozen Adjacency demo on `main` at `cd218dd` keeps working no matter
what happens to ImagineSignal, which is what makes it a safe fallback on Saturday night.

## 3. Module map

Dependency order. Nothing in an earlier row imports from a later one. See
[IS-02](diagrams/IS-02-component-lld.svg).

| Module | Lines | Responsibility | Highest evidence it can produce |
|---|---:|---|---|
| `canonical.py` | 94 | Deterministic JSON, stable SHA-256 | `UNIT_TESTED` |
| `contracts.py` | 656 | 26 frozen models, 213 fields, `extra="forbid"` | `UNIT_TESTED` |
| `ports.py` | 276 | The provider boundary. No HTTP, no credential, no env switch | `UNIT_TESTED` |
| `mutations.py` | 241 | One-axis validation, locked-attribute proof | `UNIT_TESTED` |
| `assets.py` | 328 | Content addressing, hand-rolled PNG and JPEG header parsing | `UNIT_TESTED` |
| `adapters/fixture_blobs.py` | 414 | Replay-first binary fixtures, secret scan | `FROZEN_REPLAY` |
| `adapters/xai_live.py` | 377 | Live xAI transport, **skeleton** | none yet |
| `imagine_client.py` | 467 | Fixture / Recording / Live clients, cost interlock | `FROZEN_REPLAY` |
| `outcomes.py` | 379 | Aggregate snapshots, idempotent repository | `FROZEN_REPLAY` |
| `auction.py` | 1305 | Auction sensitivity across three mechanisms | `SIMULATED` |
| `gates.py` | 604 | `IS0` through `IS8`, pure functions | gate results only |
| `decisions.py` | 157 | Evidence ceiling, deterministic action resolution | gate results only |
| `receipts.py` | 123 | Append-once, digest-linked receipts | `UNIT_TESTED` |
| `service.py` | 928 | Offline orchestration, idempotent | `FROZEN_REPLAY` + `SIMULATED` |
| `demo.py` | 271 | Deterministic artifact writer | `FROZEN_REPLAY` |

`auction.py` is the largest module and produces the weakest evidence. That asymmetry is worth
knowing before anyone asks about it.

## 4. Call-flow trace: the offline replay path

This is the path the demo runs and the one that will be on screen Saturday. Line anchors are real.

**Entry.** `scripts/run_imagine_signal_demo.py` builds an `OfflineFamilyRequest` and calls
`OfflineImagineSignalService.run` (`service.py:299`).

1. **`run` loads the frozen outcome fixture** and computes a semantic request hash
   (`service.py:302-303`).
2. **Idempotency check under a lock** (`service.py:304-316`). A repeated `idempotency_key` with the
   same hash returns the previous result. With a *different* hash it raises
   `SERVICE_IDEMPOTENCY_CONFLICT`. Replaying is safe, silently changing the input is not.
3. **`_execute` validates request contracts** (`service.py:324`).
4. **Assets are replayed** through `_replay_assets`, returning the assets, per-asset gate groups for
   `IS1`, `IS3`, and `IS4`, and the total cost in ticks (`service.py:325`). Underneath,
   `FixtureImagineClient._replay` (`imagine_client.py:128`) looks up the exact committed fixture by
   request hash. **A miss is terminal.** There is no fallback to a live call.
5. **Outcome snapshots are appended once** and each is admitted by `is5_outcome_admission`
   (`service.py:328-344`). Note the expected-experiment binding at `service.py:338`: this is the
   fix for the self-comparison defect, and an unexpected experiment now forces `HOLD`.
6. **Signal estimates per context** are computed and admitted by `is6_statistical_validity`
   (`service.py:346-359`).
7. **The auction scenario runs** and is admitted by `is7_auction_sensitivity`
   (`service.py:361-367`). Everything it returns is labeled `SIMULATED`.
8. **Mutation and budget gates** run (`service.py:369-391`). `is0_request_budget` is called with
   `mode=DeploymentMode.FIXTURE` and `allowed_modes={FIXTURE}`, so the offline path cannot even
   express a live request.
9. **All eight gate results are assembled** (`service.py:392-401`) and passed to
   `build_signal_decision` (`service.py:402`) with `evidence_class=FROZEN_REPLAY`.
10. **`build_signal_decision`** (`decisions.py:123`) recomputes `IS8` itself, refuses duplicate gate
    entries, and calls `resolve_final_action`.
11. **`resolve_final_action`** (`decisions.py:74`) takes the **most restrictive** of the proposal and
    every failed gate's `coerce_to`, using the ordering
    `TEST(0) < EDIT(1) < KEEP(2) < HOLD(3) < REVIEW(4) < STOP(5)`. One failed gate can only make the
    outcome stricter, never looser.
12. **Efficiency is computed** (`service.py:413`), a receipt id is derived from the request hash
    (`service.py:419`), and `build_decision_receipt` writes an append-once receipt
    (`service.py:422-438`).
13. **`OfflineRunResult` is returned** with a plain-English explanation string
    (`service.py:440-456`).

## 5. Call-flow trace: record and live

Both go through `_ExternalImagineClient._invoke` (`imagine_client.py:206`). The only difference is
where verified bytes land: a fixture store for RECORD, a content-addressed asset store for LIVE.

1. **`reject_fixture_secrets` scans the request** before anything else (`imagine_client.py:207`).
2. **`_admit_call`** (`imagine_client.py:177`) enforces the interlock, in this order: blocked on
   unreconciled unknown cost, call-count cap, cost cap, then per-call output cap.
3. **`self.transport.invoke(...)` runs exactly once** (`imagine_client.py:224`). No retry. No
   fallback.
4. **`ProviderOutcomeUnknownError` is caught** (`imagine_client.py:225`) and converted into an
   `UNKNOWN` result with unknown cost, which sets the reconciliation block. "The provider may have
   accepted work but I cannot confirm it" is a distinct, typed state.
5. **`_validate_transport_result`** (`imagine_client.py:321`) rejects a completed response missing a
   request id, resolved model, moderation disposition, or valid latency, and rejects any
   non-completed response carrying media.
6. **`_cost_status`** (`imagine_client.py:194`) records exact ticks or sets
   `_cost_reconciliation_blocked = True`. **It never records zero for an unreported cost.**
7. **RECORD** writes a sanitized fixture (`imagine_client.py:279`). **LIVE** validates and persists
   bytes through `_store_live_assets` (`imagine_client.py:353`).

The live path was exercised end to end during the dry run with a local fake transport and zero
network. All 17 checks passed. See [20_DRY_RUN_REPORT.md](20_DRY_RUN_REPORT.md) section 8.

## 6. Module interaction matrix

Rows call columns. `port` marks a call that crosses the provider boundary.

| calls → | canonical | contracts | ports | mutations | assets | blobs | client | outcomes | auction | gates | decisions | receipts |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `contracts` | x | | | | | | | | | | | |
| `mutations` | | x | | | | | | | | | | |
| `assets` | | x | | | | | | | | | | |
| `fixture_blobs` | | | x | | x | | | | | | | |
| `xai_live` | | | **port** | | | | | | | | | |
| `imagine_client` | | | **port** | | x | x | | | | | | |
| `outcomes` | | x | | | | | | | | | | |
| `auction` | | x | | | | | | | | | | |
| `gates` | | x | | x | | | | | | | x | |
| `decisions` | | x | | | | | | | | x | | |
| `receipts` | x | x | | | | | | | | | | |
| `service` | x | x | x | x | | | x | x | x | x | x | x |

`gates` and `decisions` are mutually recursive by design: `gates.is8_evidence_action` calls
`decisions.evidence_capped_action`, and `decisions.build_signal_decision` imports
`gates.is8_evidence_action` *inside the function body* (`decisions.py:135`) to break the import
cycle. That local import is deliberate, not an oversight.

## 7. What crosses the boundary, and what never does

| Crosses the port | Never crosses |
|---|---|
| A validated `ImagineRequest` | A credential. `ports.py` has no credential lookup at all |
| A typed `TransportResult` | Raw base64 or a signed URL into any log, fixture, or artifact |
| Decoded image bytes, immediately hashed | A provider URL as the only record of an asset |
| Exact cost ticks, or an explicit unknown | An inferred or estimated cost |

## 8. Expected results from the hackathon

Split by what is already true, what is likely, and what is a stretch. Each carries the evidence class
it will legitimately support. Nothing here should be stated more strongly than its row allows.

### Committed, true before the event starts

| Result | Evidence | How it is shown |
|---|---|---|
| Deterministic offline pipeline, control plus two one-axis variants | `FROZEN_REPLAY` | `run_imagine_signal_demo.py --verify-only`, artifact digest `b17e9105...` |
| Nine fail-closed gates, decision core at 100 percent line and branch | `UNIT_TESTED` | CI gate 1 |
| Append-once receipts with tamper detection | `UNIT_TESTED` | `tests/imagine_signal/test_receipts.py` |
| Auction sensitivity across three mechanisms | `SIMULATED` | `test_auction.py`, labeled everywhere |
| Cost interlock that halts on unknown spend | `UNIT_TESTED` | dry-run probe, 17/17 |

### Probable, if Friday's preflight succeeds

| Result | Evidence it would carry | Depends on |
|---|---|---|
| Live transport implemented, both xfail markers deleted | `UNIT_TESTED` | Provider field names from one smoke call |
| One real controlled family generated end to end | `LIVE_PROVIDER` origin, still not causal | API credit on the team |
| **Measured cost per qualified output** | Real, from reported ticks | Enough calls to be meaningful |
| Moderation disposition recorded on a real response | observed | Provider exposing the field |

Cost per qualified output is the number worth saying out loud. It is measured rather than asserted,
and it is the efficiency claim the product is actually about.

### Stretch

| Result | Risk |
|---|---|
| **An ImagineSignal demo surface** | **It does not exist today.** `app.py` launches only the base Adjacency Autopsy demo, and `ui.py` never imports `imagine_signal`. This is the single largest demo risk. |
| Theme-aligned extension | Theme is unannounced as of 2026-08-05 |
| Multi-image edit family | P1 in the integration note, raises the chance more than one factor changes |

### What will not be true, whatever happens

No causal lift, no image-quality claim, no advertiser-lift claim, no production readiness, and no X
revenue figure of any kind. Replay and simulation cannot supply that evidence, which is why the
action ceiling is `TEST` and why nine production blockers are named in
[12_IMPLEMENTATION_STATUS.md](12_IMPLEMENTATION_STATUS.md).

### On the test count

The suite reports **448 passed, 2 xfailed** in a fully equipped environment and **446 passed, 1
skipped, 2 xfailed** in one built from `pip install -e ".[test,serve]"`. The difference is
`temporalio`, which lives in a separate extra, so `tests/test_temporal_hitl.py` skips. Both are
correct. Knowing this in advance prevents a wasted twenty minutes on Saturday.

## 9. Where to go next

- Visual walkthrough: [`system_design.html`](system_design.html)
- Every symbol: [17_API_REFERENCE.md](17_API_REFERENCE.md)
- Saturday commit plan: [18_HACKATHON_PUSH_STRATEGY.md](18_HACKATHON_PUSH_STRATEGY.md)
- Cursor and Grok working rules: [19_CURSOR_XAI_GROK.md](19_CURSOR_XAI_GROK.md)
- Presentation brief: [15_DESIGN_HANDOFF.md](15_DESIGN_HANDOFF.md)
- What was actually verified: [20_DRY_RUN_REPORT.md](20_DRY_RUN_REPORT.md)
- The one file a teammate reads: [`../../hackathon/GROK_RUNBOOK.md`](../../hackathon/GROK_RUNBOOK.md)
