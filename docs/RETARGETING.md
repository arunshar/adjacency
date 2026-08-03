# Retargeting Adjacency to a different domain

Adjacency is presented as brand safety for advertising, but that is the application, not the engine.
This document names exactly what changes if you point it somewhere else, because the question "is
this general or did you build one thing" deserves a concrete answer.

## What is already domain-free

The logic in `src/adjacency/gates.py` contains no domain knowledge at all:

- **G0** checks that a compiled clause quotes its source prose verbatim.
- **G1** checks that a cited text span is present byte-for-byte and a cited box lies inside its frame.
- **G2** checks that a cited rule exists at the stated policy version.
- **G3** blocks a revision that would loosen decisions on a frozen holdout without logged approval.
- **G4** checks that the action matches the severity table.
- **G5** enforces token, tool-call, and wallclock budgets.
- **G6** refuses to allow anything below a confidence floor or when two effort levels disagree.

None of that is about advertising. It is: compile a policy from prose, judge content against it,
verify the model cited real evidence, and refuse to fail open. That shape applies to content
moderation, compliance review, document classification, safety filtering, and grading.

The same is true of the escalation ladder, the fixture recorder, the near-duplicate clustering, the
delta engine, and the fault-injection eval harness.

## What is domain-shaped, and where

The vocabulary is advertising-specific in a small number of places. All of it is naming, not behavior.

| Where | Currently | Generic equivalent |
|---|---|---|
| `contracts.py`, `PolicySpec.advertiser` | the party whose policy this is | `owner` |
| `contracts.py`, `InventoryItem` | a unit of content an ad could appear beside | `ContentItem` |
| `contracts.py`, `DeltaKind.OVER_BLOCK` / `UNDER_BLOCK` | vs. a keyword baseline | keep, or `FALSE_POSITIVE` / `FALSE_NEGATIVE` |
| docstrings throughout | reference ads, impressions, blocklists | reword |

## The actual retargeting procedure

1. Rename `advertiser` to `owner` and `InventoryItem` to `ContentItem`. Mechanical, and the test suite
   catches anything missed.
2. Replace the baseline. `BaselineMatcher` compares against a keyword blocklist because that is what
   the advertising product ships. In another domain, the baseline is whatever the incumbent method is,
   generated from the same source policy so the comparison stays honest.
3. Repoint the corpus. `ADJ_SOURCE` already abstracts this behind four tiers.
4. Rewrite the severity table in `contracts.py` if the new domain has different consequences.

Everything else, including all seven gates and every test in `tests/test_gates.py`, carries over
unchanged.

## The honest limit

Two assumptions are baked in and would need real work to remove.

**Evidence is text spans or image boxes.** A domain whose evidence is audio timestamps, video frame
ranges, or table cells needs a new `Evidence` variant and a matching G1 branch. The `Evidence` union is
deliberately small so adding one fails type checking loudly rather than silently.

**Decisions are a three-way ALLOW, BLOCK, REVIEW.** A domain needing graded scores rather than actions
would change `Action` and the severity table, and G4 would need rethinking rather than renaming.
