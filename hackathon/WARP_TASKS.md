# Warp task queue and model allocation

| Field | Value |
|---|---|
| Version | **2.0** |
| Prepared | 2026-08-05, rewritten 2026-08-06 |
| Budget | 7,000 Warp credits. Task 1 of v1.0 cost **205** on `auto (cost-efficient)` |
| Allocation rule | **By blast radius, not by benchmark** |

> **v1.0 is complete.** Tasks 1 through 5 of the old queue all shipped: the demo surface, the canary
> preparation, the smoke call, `extract_provider_response`, and `XAIImagineTransport.invoke`. Do not
> rebuild them. What remains is one cleanup job and Saturday.

## 1. The allocation rule

The question is never "is this model good enough?" It is **"if this output is silently wrong, what
catches it?"**

| Tier | Model | Work | What catches a mistake |
|---|---|---|---|
| **Never delegate** | none | `gates.py`, `decisions.py`, `contracts.py`, `canonical.py`, `receipts.py`, `mutations.py`, `ports.py` (both packages), and the cost accounting in `imagine_client.py` | **Nothing. These are the checking layer.** Arun writes them or they do not change |
| **Strong** | best you have | `adapters/xai_live.py`, any contract or schema change, Saturday's core decision logic | Contract tests catch shape errors. Semantics still need judgment |
| **Cheap** | value model | Docs, prose, fixtures, UI, scripts, slide copy, retarget renames | The full suite, the artifact digest, and a human read |

**Why a cheaper model is genuinely safe in the cheap tier here.** Three independent backstops exist:
the deterministic core is at 100 percent line and branch so an invariant break cannot pass; the
artifact SHA-256 detects any drift in decision logic from the outside; and
`tests/hackathon/test_xai_live_contract.py` now pins the transport with **50 tests**, up from the 15
plus 2 strict-xfails it carried in v1.0. The risk of a weaker model is **extra iterations**, not
undetected defects.

The calibration probe from v1.0 is no longer needed. The measured answer is in the budget row above:
205 credits for a real task on the cost-efficient tier, so 7,000 is comfortable. **Keep the reserve
rule: do not drop below 40 percent of the balance before Saturday 09:00.** The assigned brief is the
only unbounded item in the whole plan.

## 2. What the checking layer now includes

Read this before you trust a green result. Four guards in this repository have failed **silently**,
and every one of them kept reporting success while measuring the wrong thing:

| Guard | How it failed | Fixed by |
|---|---|---|
| `verify_tree.sh` core check | BRE regex `\(a\|b\)` under `grep -E`, which matches nothing | ERE alternation |
| `verify_tree.sh` core check | Scanned untracked paths only, so it stopped guarding once work was committed | Also scan `git diff --name-only` |
| `verify_tree.sh` git block | Kept printing `expected cd218dd` and `expected 0 unpushed` after the branch moved and was pushed | Check `main` never moves, and compare against the branch's own upstream |
| Backup manifest | Described a bundle one commit behind as carrying "the full commit" | Bundle refreshed, patch relabelled HISTORICAL |

**None of them crashed.** The lesson to carry into Saturday: test a guard by breaking the thing it
guards, never by running it on a clean tree. A guard you have only ever seen pass is a guard you
have never tested.

## 3. The queue

### Task A: delete the dead URL-fetch machinery

**Tier:** cheap. **Blocked by:** nothing. **Do this before Saturday, not during.**

The base64 migration made an entire code path unreachable. `src/adjacency/imagine_signal/adapters/xai_live.py`
still carries `fetch_provider_media`, `_host_allowed`, `_assert_host_resolves_public`,
`ALLOWED_MEDIA_HOSTS`, `ALLOWED_MEDIA_TYPES`, the no-redirect handler, and the `MediaFetcher`
protocol. Each is marked `UNREFERENCED 2026-08-06` in its docstring.

**This is not a one-line cut.** Four tests in `tests/hackathon/test_xai_live_contract.py` still
import and exercise the machinery, around lines 24 to 42 and 624 to 676. Deleting the source without
the tests breaks the suite at import time. Delete both together, or leave both alone.

Judge whether it is worth doing at all. The argument for: dead security-shaped code invites a future
reader to call it, and it already caused one CI failure through a `B101` assert inside it. The
argument against: it is inert, it is clearly labelled, and `COST_LEDGER.md` already recorded the
decision to defer. **If you are not confident, leave it and say so.** Deleting working code the night
before an event is how demos break.

**Acceptance:** 488 tests minus exactly the tests you deliberately removed, `bandit` exit 0, `ruff`
clean, artifact digest unchanged, and `./hackathon/verify_tree.sh` reporting no core-file change.

### Task B: Saturday, the assigned brief

**Tier:** mixed. **Blocked by:** the 09:00 brief. **This is the whole job.**

Follow `hackathon/CONTINGENCY.md`. The shape of the day:

1. **09:00.** Read the brief. Answer one question honestly: *does it involve a model or agent
   producing an output somebody has to trust?*
2. **09:15.** Commit to reuse-or-fresh and **do not revisit it at noon.** A reversed decision at
   13:00 costs more than either choice made at 09:00.
3. **Yes** means the 90-minute mechanical retarget in `CONTINGENCY.md` section 5, driven by
   `docs/RETARGETING.md`. **Partly** means drop gates and receipts into the one component that needs
   defending. **No means start fresh and do not force it.** Bolting a verification harness onto a
   brief that does not need one reads as "he had a hammer" and scores worse than a clean small build.
4. **Keep `IS0` through `IS8` out of it** unless the brief is genuinely about creative generation.
5. **21:00 hard feature freeze.** Event ends Sunday 01:00.

The provider ladder in `CONTINGENCY.md` section 3 covers every access scenario from no network to a
key they hand out. `tier_zero.decide_tier_zero` makes decisions with no model at all, and the Autopsy
demo has been verified running with wifi off. **You are never without a demo.**

## 4. Per-task prompt template

```text
Read WARP.md and hackathon/WARP_HANDOFF.md first if you have not this session.

Task: <paste one task from hackathon/WARP_TASKS.md>

Before editing: run the checkpoint commands in hackathon/WARP_BOOTSTRAP.txt and confirm
branch canary/imagine-signal, HEAD 94a1d27, clean status, 488 passed.
While editing: touch no file in the undelegatable list.
After editing: run ./hackathon/verify_tree.sh, then ruff check src tests scripts and
ruff format --check src tests scripts, then bandit -q -c pyproject.toml -r src, then the
full suite and the artifact digest. Show me every output verbatim.

Do not run any git command that writes. Do not make a provider call. Plain ASCII hyphens
only. Report what you verified and, explicitly, what you did not.
```

**Why bandit is in that list now.** It is a CI gate, it is the one gate that has actually failed, and
it is not covered by the test suite. Running the suite and calling it green is exactly the mistake
that produced the failed pull request #9.

## 5. Tracking spend

| Task | Model | Credits before | Credits after | Cost | Iterations | Accepted? |
|---|---|---:|---:|---:|---:|---|
| v1.0 task 1 | auto (cost-efficient) | | | **205** | | yes |
| A | | | | | | |
| B (Saturday) | | | | | | |

Only the 205 is measured. The current balance was never recorded, so read it from the account before
Saturday rather than assuming 7,000 minus what this table shows.

At roughly 200 credits per substantial task, the reserve rule is not a binding constraint. Spend the
strong tier freely on Saturday's decision logic, which is the one place judgment is not backstopped
by an existing test.
