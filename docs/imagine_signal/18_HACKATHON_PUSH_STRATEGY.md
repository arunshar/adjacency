# Hackathon push strategy

| Field | Value |
|---|---|
| Version | 1.0 |
| Event | Saturday 2026-08-08, 09:00 to Sunday 01:00 |
| Branch | `canary/imagine-signal`. `main` stays at `cd218dd` |
| Governing rule | **Every commit must leave a demoable repository behind it** |

Diagram: [IS-05](diagrams/IS-05-push-timeline.svg).

## The principle

Order commits so that the thing most likely to fail comes *after* the thing most likely to impress.
At every tag you should be able to stop, present, and be honest about where you got to. That is why
the already-green offline MVP ships at 09:00 rather than at the end.

Ask of every commit: **if everything after this fails, what is still true?** If the answer is
"nothing demoable", the commit is in the wrong place.

## The trap, restated

`.github/workflows/ci.yml` triggers only on `pull_request` and on `push` to `main`.

**Pushing `canary/imagine-signal` runs zero checks.** You get a green-looking branch with nothing
behind it. Open a **draft PR into `main`** immediately after the first push. It runs the full matrix,
merges nothing, and re-runs on every subsequent push, giving you a free continuous check all day.

## Commit sequence

### C1, 09:00. The canary

```text
Add ImagineSignal offline MVP and the Grokathon live-transport seam

Offline MVP only. Evidence is UNIT_TESTED, FROZEN_REPLAY, and SIMULATED.
No live xAI call, no X Ads read, no publish, no spend. Production is NO_GO
and the action ceiling is TEST. The live transport is a skeleton with an
executable contract and two strict-xfail specs.
```

**Rationale.** Everything in it is already verified: 448 passed, both CI gates green, artifact digest
`b17e9105...`. Landing it first converts several days of work into something a judge can clone
before you have written a line under time pressure.

**If everything after this fails:** you still have a complete, tested, honest offline system with
receipts and gates, plus 16 documents and 5 diagrams. That is a real submission.

Then: draft PR, wait for green, `git tag -a v0.3.0-canary`, `gh release create --prerelease`.

**Rollback:** delete the branch and tag. `main` never moved.

### C2, ~10:00. The provider field map

```text
Record the verified xAI Imagine response field map

Fills the UNVERIFIED table in hackathon/COST_LEDGER.md from one authorized
smoke call. No library code changes. Documents the actual cost path, the
image field, and the moderation disposition name.
```

**Rationale.** This is documentation, not code, and it is the input everything else needs. Committing
it separately means the discovery survives even if the implementation goes badly, and a teammate can
pick up the transport without repeating a paid call.

**If everything after this fails:** the next session starts from transcription rather than discovery.

### C3, ~11:30. The live transport

```text
Implement the live xAI Imagine transport

Fills extract_provider_response and XAIImagineTransport.invoke against the
recorded response shape. Deletes both strict-xfail markers in
tests/hackathon/test_xai_live_contract.py, which now assert real behavior.
One request per call, no retry, no fallback.
```

**Rationale.** The seam is one class with one method and everything downstream is already proven
against it, including a zero-network run of the whole live path during the dry run. Deleting the
xfail markers in the *same* commit is the discipline: strict xfail turns an unexpected pass into a
failure precisely so the exemption cannot be left behind.

**If everything after this fails:** you can say the live path is implemented and tested, which is a
materially stronger claim than the offline MVP alone.

Then: `git tag -a v0.3.1-canary`.

### C4, ~13:00. The first real controlled family

```text
Add the first live controlled creative family

One approved base, two variants changing only the declared axis, generated
through the live transport under an approved cost-capped policy. Records
lineage, actual reported cost, and a decision receipt. Evidence remains
non-causal: this is a real generation, not a measured lift.
```

**Rationale.** This is the demo moment. It is also the first commit where cost per qualified output
becomes a **measured** number rather than an accounting capability.

**If everything after this fails:** you have a live end-to-end run with a receipt. That is the story.

### C5, ~15:00. The demo surface. **Time-boxed, hard stop at 17:00**

```text
Add a minimal ImagineSignal demo surface

Extends the existing Gradio app with an ImagineSignal view: the controlled
family, which attribute changed, per-generation cost, the gate ladder, and
the final action from the receipt. Read-only. No control triggers a
generation or a spend.
```

**Rationale, and the honest part.** *This does not exist today.* `app.py` launches only the base
Adjacency Autopsy demo, and `ui.py` never imports `imagine_signal`. The dry run confirmed it. It is
the single largest demo risk and it is scheduled here on purpose, late enough that nothing depends on
it and early enough to finish.

**Hard stop at 17:00.** If it is not working, abandon it and demo the CLI artifact plus the Autopsy
UI. Do not let a UI eat the evening. A CLI that prints a verified receipt is a perfectly good demo.

### C6, ~17:00. Theme alignment

```text
Extend ImagineSignal for the announced Grokathon theme

Built on the existing gates and evidence classes rather than beside them.
No new claim class and no new evidence class.
```

**Rationale.** The theme is unannounced as of 2026-08-05. Whatever it is, extend through the existing
gate chain. A theme-specific bolt-on that bypasses the gates would undo the thing that makes the
project interesting.

### C7, 21:00. Freeze

```text
Freeze the Grokathon submission

Records final artifact digests, the cost ledger totals, and the exact
evidence class of every claim in the submission.
```

**Feature freeze is 21:00 and it is not negotiable.** After it: documentation, digests, and the
demo rehearsal only. A working demo at 21:00 beats a broken better one at midnight.

## Tag ladder

| Tag | After | Guarantees |
|---|---|---|
| `v0.3.0-canary` | C1 | Offline MVP, all gates, full docs |
| `v0.3.1-canary` | C3 | Live transport implemented and tested |
| `v0.3.2-canary` | C4 | One real family with a receipt |
| `v0.3.3-canary` | C5 or C6 | Whatever landed before the freeze |
| `v0.4.0-canary` | C7 | The submission |

Tag at every stable point. It costs seconds and guarantees a recent known-good commit to demo from.

## Rollback per stage

| Stage | Rollback |
|---|---|
| Any commit | `git revert` on the canary branch. Never force-push a branch a teammate has cloned |
| A whole tag | `gh release delete`, `git push origin :refs/tags/<tag>` |
| The entire canary | Delete branch and tag. `main` at `cd218dd` is untouched |
| Total failure | `git checkout cd218dd`, run the offline Adjacency demo. Verified working with wifi off |

The rollback sequence was rehearsed against a local bare remote during the dry run and left nothing
behind.

## What must not happen

1. **No push to `main`.** The frozen demo is the floor.
2. **No commit that makes an unsupported claim** in its message. Commit messages are read by judges.
3. **No live call outside an approved `ExternalCallPolicy`.** The code refuses anyway.
4. **No retry loop added under time pressure.** One invocation per call is a designed property.
5. **No deleted xfail marker without the implementation** that earns it.
6. **No feature after 21:00.**
