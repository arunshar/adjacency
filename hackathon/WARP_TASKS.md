# Warp task queue and model allocation

| Field | Value |
|---|---|
| Version | 1.0 |
| Prepared | 2026-08-05 |
| Budget | 7,000 Warp credits |
| Allocation rule | **By blast radius, not by benchmark** |

## 1. The allocation rule

The question is never "is this model good enough?" It is **"if this output is silently wrong, what
catches it?"**

| Tier | Model | Work | What catches a mistake |
|---|---|---|---|
| **Never delegate** | none | `gates.py`, `decisions.py`, `contracts.py`, `canonical.py`, `receipts.py`, `mutations.py`, `ports.py` (both packages), and the cost accounting in `imagine_client.py` | **Nothing. These are the checking layer.** Arun writes them or they do not change |
| **Strong** | best you have | `adapters/xai_live.py`, any contract or schema change, Saturday's core decision logic | Contract tests catch shape errors. Semantics still need judgment |
| **Cheap** | value model | Docs, prose, fixtures, the demo surface, scripts, slide copy, retarget renames | The full suite, the artifact digest, and a human read |

**Why a cheaper model is genuinely safe in the cheap tier here.** Three independent backstops exist:
the deterministic core is at 100 percent line and branch so an invariant break cannot pass; the
artifact SHA-256 detects any drift in decision logic from the outside; and
`tests/hackathon/test_xai_live_contract.py` pins the transport with 15 tests plus 2 strict-xfail
specs. The risk of a weaker model is **extra iterations**, not undetected defects.

## 2. Task 0: calibrate before committing the budget

Do this first. It converts an unknown per-model credit cost into a real number from the account.

1. Record the starting credit balance.
2. Run **task 1** on the candidate value model. Real work, safe tier, objective acceptance test.
3. Record credits consumed and iterations needed.
4. Run the **hard probe**: hand the same model task 4 with only
   `tests/hackathon/test_xai_live_contract.py::test_extract_preserves_completion_invariants` as the
   spec. Count iterations to green.

**The probe is the decision.** Three iterations or fewer means the value model is fine for the strong
tier too, and 7,000 credits goes a long way. Thrashing means keep it for the cheap tier and spend the
strong model on tasks 4 and 5 only, which are two functions.

> **Reserve rule: do not drop below 40 percent of the balance before Saturday 09:00.** The assigned
> brief is the only unbounded item. Running out at 14:00 on the day is far worse than paying more for
> a stronger model on two functions.

## 3. The queue

Work in order. Do not jump ahead of a blocked task.

### Task 1: the ImagineSignal demo surface

**Tier:** cheap. **Blocked by:** nothing. **This is the largest known gap.**

`app.py` launches only the base Adjacency Autopsy demo, and `src/adjacency/ui.py` never imports
`imagine_signal`. Confirmed by running the app during the dry run.

Build a read-only ImagineSignal view. Extend the existing Gradio app rather than starting a second
one. It must show:

- The controlled family: control plus two variants, from the frozen fixtures.
- Which attribute changed, named explicitly, and which attributes stayed locked.
- Per-generation cost from the artifact, with its status.
- The gate ladder `IS0` through `IS8` with pass or fail and any coercion.
- The final action from the receipt, and the evidence class that permitted it.

**Constraints.** Read-only. No control may trigger a generation, a spend, or any provider call. Read
the existing artifact and fixtures, do not regenerate them. Follow the visual language already in
`src/adjacency/ui.py`.

**Acceptance:**

```bash
cd /Users/arunsharma/code/adjacency && env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python app.py
```

Loads, the ImagineSignal view renders from frozen data, the suite still reports `448 passed, 2
xfailed`, and the artifact digest is unchanged.

### Task 2: Friday canary preparation

**Tier:** cheap. **Blocked by:** nothing.

Verify every command in `hackathon/CANARY_RELEASE.md` is correct against the current tree: the file
set the commit would capture, the branch and tag names, and the draft-PR command. **Report the
commands. Do not run any of them.** Arun executes all git writes.

Remember the trap: `.github/workflows/ci.yml` triggers only on `pull_request` and `push` to `main`,
so pushing the canary branch alone runs zero checks. The draft PR is what runs CI.

### Task 3: the smoke call. **Arun only, not you**

**Tier:** human. **Blocks:** tasks 4 and 5.

Arun runs `hackathon/smoke_call.py` once, with a cost cap, and pastes the raw response into the
UNVERIFIED field-map table in `hackathon/COST_LEDGER.md`.

**You must not run this.** It is a paid external call. Until the table is filled, tasks 4 and 5 stay
blocked. That gating is the entire reason two functions are unimplemented rather than guessed.

### Task 4: `extract_provider_response`

**Tier:** strong. **Blocked by:** task 3.

Implement `extract_provider_response` in `src/adjacency/imagine_signal/adapters/xai_live.py` from the
real recorded response. The docstring carries the full specification. Required order: moderation
rejection first, then `usage.cost_in_usd_ticks`, then image bytes, then `provider_request_id`,
`provider_model_resolved`, and `moderation_respected`.

**Acceptance:** replace the placeholder raw response in
`test_extract_preserves_completion_invariants`, delete its `xfail(strict=True)` marker, and the test
passes. Never write raw base64 or a signed URL into a log, fixture, or artifact.

### Task 5: `XAIImagineTransport.invoke`

**Tier:** strong. **Blocked by:** task 4.

Implement the HTTP body. The docstring gives the six-step sequence. Exactly one request. No retry, no
fallback. On a timeout or ambiguous failure after the request was sent, raise
`ProviderOutcomeUnknownError` with the provider request id.

**Acceptance:** delete the second `xfail(strict=True)` marker and the suite moves from `448 passed, 2
xfailed` to `450 passed`. Lift the `_unverified` entries in `build_request_body` to the top level
once the field names are confirmed.

### Task 6: Saturday

**Tier:** mixed. **Blocked by:** the 09:00 brief.

Follow `hackathon/CONTINGENCY.md`. Make the reuse-or-fresh decision at 09:00, commit to it by 09:15,
and do not revisit it at noon. Feature freeze at 21:00.

## 4. Per-task prompt template

```text
Read WARP.md and hackathon/WARP_HANDOFF.md first if you have not this session.

Task: <paste one task from hackathon/WARP_TASKS.md>

Before editing: run the three verification commands and confirm the checkpoint.
While editing: touch no file in the undelegatable list.
After editing: run ./hackathon/verify_tree.sh, then ruff check src tests scripts and
ruff format --check src tests scripts, then the full suite and the artifact digest.
Show me all three outputs verbatim. git status is NOT sufficient here: it hides changes
inside untracked directories, and most of this repo is untracked on purpose.

Do not run any git command that writes. Do not make a provider call. Do not delete an xfail marker
without the implementation that earns it. Plain ASCII hyphens only.

Report what you verified and what you did not.
```

## 5. Tracking spend

Append a row per task. The point is to learn the real conversion rate early, not to audit afterwards.

| Task | Model | Credits before | Credits after | Cost | Iterations | Accepted? |
|---|---|---:|---:|---:|---:|---|
| 1 | | | | | | |
| 4 probe | | | | | | |
| 2 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |

After tasks 1 and the probe, extrapolate. If the projected total for tasks 2 through 5 exceeds 40
percent of the remaining balance, drop to the cheaper model for everything except tasks 4 and 5.
