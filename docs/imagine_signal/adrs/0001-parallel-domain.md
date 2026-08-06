# ADR 0001: Isolate ImagineSignal in a parallel domain package

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-08-05 |
| Author | Arun Sharma |
| Deciders | Engineering lead and Adjacency maintainer, TBD |
| Reviewers | Product, Ads science, Imagine API, security |

## Context

The existing Adjacency domain decides whether an ad may be served next to a piece of inventory. Its public vocabulary includes `ALLOW`, `BLOCK`, `REVIEW`, `Verdict`, `InventoryItem`, `DeltaKind`, and G0-G6 safety gates.

ImagineSignal decides whether a generated creative family has valid lineage and enough evidence for another creative action. Its vocabulary includes campaign, mutation, asset, outcome, simulation, evidence class, and next action.

Both domains benefit from immutable contracts, stable hashes, deterministic gates, fixture replay, near-duplicate checks, and human review. Their decisions and failure directions are not interchangeable.

## Options considered

### Option A: Extend current Adjacency contracts and gate chain

Add creative actions to `Action`, creative fields to `Verdict` or `InventoryItem`, and new meanings to G0-G6.

Advantages:

- Fewer initial files.
- Direct access to existing orchestration.

Disadvantages:

- Changes public safety semantics.
- Makes `ALLOW` and `BLOCK` ambiguous between inventory serving and creative promotion.
- Risks breaking the current demo, artifacts, and quality claims.
- Couples creative evolution to the brand-safety release surface.

### Option B: Add a parallel bounded package in the same repository

Create `adjacency.imagine_signal` with separate contracts, gates, decisions, receipts, ports, and adapters. Reuse current patterns by composition or neutral helpers.

Advantages:

- Preserves existing public behavior.
- Reuses tested engineering discipline.
- Makes cross-domain integration explicit.
- Supports separate code ownership and release cadence later.
- Keeps the hackathon implementation easy to review in one repository.

Disadvantages:

- Some duplicate scaffolding until neutral utilities are extracted.
- Requires careful dependency direction.
- The repository name may eventually understate the expanded product scope.

### Option C: Build a separate repository and service immediately

Create a new standalone service with duplicated or packaged Adjacency utilities.

Advantages:

- Strong isolation and independent deployment.
- Freedom to select a different stack.

Disadvantages:

- More setup before proving the deterministic concept.
- Easy to drift from the current gates and replay discipline.
- Requires packaging, versioning, authentication, deployment, and shared-contract decisions before the MVP.

## Decision

Choose Option B.

Create a parallel `src/adjacency/imagine_signal/` package. Do not modify existing `Action`, `Verdict`, `InventoryItem`, `DeltaKind`, G0-G6 codes, or Autopsy artifact semantics for creative optimization.

Reuse:

- The frozen Pydantic model pattern.
- NFC normalization where exact spans matter.
- Canonical hashing behavior, extracted into a public neutral helper rather than importing private `_stable_hash`.
- FixtureStore for compatible JSON control-plane calls, after adding response scanning for the new surface.
- Near-duplicate primitives as coarse filters.
- Human-review protocol shape.
- The quality policy of complete deterministic-core coverage and fixture replay for I/O.

Create separate `IS0` through `IS8` creative gate codes and `NextAction` values.

## Consequences

### Positive

- Existing Adjacency behavior and claims remain reviewable and stable.
- Creative decisions can evolve without widening the brand-safety contract.
- Integration points become typed instead of implicit.
- A later service extraction remains possible behind ports.

### Negative

- The first implementation contains additional contracts and adapters.
- Shared helpers need explicit ownership and regression tests.
- Reviewers must understand two gate vocabularies.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Shared helper change breaks Adjacency | Preserve existing vectors and run full current suite |
| Package imports provider dependencies into the core | CI import test with base and test extras only |
| Similar gate names confuse receipts | Use `IS` prefix and domain label everywhere |
| Parallel code duplicates defects | Extract only small, proven neutral helpers after tests exist |

## Implementation notes

The first code slice contains only `canonical.py`, `contracts.py`, and tests. Provider, storage, service, and UI dependencies remain outside the deterministic core.

## Review trigger

Revisit if ImagineSignal becomes an independently owned or deployed service, or if a shared contracts library is required by multiple repositories.

