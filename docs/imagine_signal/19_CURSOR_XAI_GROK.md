# Working from Cursor with the xAI API, and what to trust Grok with

| Field | Value |
|---|---|
| Version | 1.0 |
| Written | 2026-08-05 |
| Premise | Grok is unreliable for this codebase's critical paths. Task allocation must reflect that rather than hope otherwise. |

Two separate things get conflated and should not be:

1. **Grok as a coding assistant inside Cursor**, writing this repository's Python.
2. **The xAI Imagine API as a runtime dependency**, generating ad images.

They have different failure modes and different blast radii. This document covers both.

---

## Part 1: driving the project from Cursor

### Credential handling

The rule is the same as everywhere else in this project: **the key lives in the environment, never in
a file the repository can see.**

```bash
export XAI_API_KEY="$(security find-generic-password -s xai_api_key -w)"
```

- Do not put the key in Cursor workspace settings. Those live in `.vscode/` or `.cursor/` and get
  committed by accident.
- Do not paste the key into a chat panel. Chat transcripts sync.
- `.env` is git-ignored. Verify with `git check-ignore -v .env` before you trust it.
- The library never reads a credential. `ports.py` has no credential lookup at all, and
  `hackathon/smoke_call.py` refuses to run unless `XAI_API_KEY` is already exported.

### Context files to keep open

Cursor's suggestion quality is mostly a function of what is in the context window. For this
repository, open these and leave them open:

| File | Why |
|---|---|
| `CLAUDE.md` | The controlling rules. Any assistant that has not read it will suggest a commit. |
| `docs/imagine_signal/16_MASTER_EXPLAINER.md` | Architecture and the call-flow traces |
| `src/adjacency/imagine_signal/ports.py` | The typed boundary that constrains everything |
| `src/adjacency/imagine_signal/adapters/xai_live.py` | Where Saturday's work happens |
| `tests/hackathon/test_xai_live_contract.py` | The executable spec |
| `hackathon/COST_LEDGER.md` | The field map, once filled |

### Verify before accepting any edit

Read-only, fast, and they catch the failure modes that matter:

```bash
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/pytest -m "not e2e" -q
```

```bash
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
```

```bash
shasum -a 256 artifacts/imagine_signal/offline_demo.json
```

If the artifact digest moves and you did not intend it, an assistant changed decision logic. Do not
regenerate to make it match. Investigate.

### The paste-in system prompt

```text
You are working in /Users/arunsharma/code/adjacency, an intentionally dirty, uncommitted review
worktree. Do not commit, stage, push, open a pull request, reset, clean, stash, or discard anything
unless I explicitly ask for that exact action.

Read CLAUDE.md and docs/imagine_signal/16_MASTER_EXPLAINER.md before proposing changes.

Hard rules. Do not make a live xAI or X Ads call. Do not read XAI_API_KEY or enable ADJ_RECORD. Do
not add a retry or fallback path to the Imagine transport. Do not weaken a gate, a contract, or an
evidence label. Do not record a cost of zero for an unreported provider cost. A missing fixture is
terminal and must never fall back to a live call.

Keep base Adjacency G0 through G6 unchanged. Keep ImagineSignal isolated under
src/adjacency/imagine_signal with IS0 through IS8. Use plain ASCII hyphens, never em or en dashes.

Never claim live Grok image quality, image-quality lift, advertiser lift, causal lift, production
readiness, or X revenue. Evidence classes are UNIT_TESTED, FROZEN_REPLAY, and SIMULATED. The action
ceiling is TEST.

When you change logic, update its tests in the same edit. State exactly what you verified and what
you did not.
```

---

## Part 2: what to give Grok, and what not to

### The allocation, by blast radius

The question is not "is Grok good?" It is **"if this suggestion is silently wrong, what catches
it?"**

> **This tiering is vendor-independent and now also governs Warp.** It was always about blast radius
> rather than about a specific model, so it applies unchanged to Grok in Cursor, to whatever model
> runs in Warp, and to anything else. The Warp-specific queue and credit strategy live in
> [`../../hackathon/WARP_TASKS.md`](../../hackathon/WARP_TASKS.md).

| Tier | Give to Grok? | Files and tasks | What catches a mistake |
|---|---|---|---|
| **Safe** | Yes, freely | Docstrings, README and doc prose, slide wording, commit-message drafts, prompt copy for mutation levels, test-name brainstorming, error-message wording | A human reading it. A wrong word costs nothing. |
| **Reviewed** | Yes, then read it | `scripts/generate_imagine_signal_fixtures.py`, demo ergonomics, plotting, CLI flags, the Gradio surface, non-gate helpers in `service.py` | The gates, plus the existing tests. A bad I/O layer still produces a verdict the gates check. |
| **Never** | No | `gates.py`, `decisions.py`, `contracts.py`, `canonical.py`, `receipts.py`, `mutations.py`, `ports.py`, the cost accounting in `imagine_client.py`, any evidence label | **Nothing.** These *are* the checking layer. |

### Why the architecture makes this a real distinction

This is not caution for its own sake. It follows from how the repository is tested, and it is worth
being able to say out loud in an interview:

- The deterministic core is held at **100 percent line and branch** in CI. The rest of the package
  has a **55 percent** floor and currently sits near 87 percent.
- That asymmetry is deliberate. The comment in `pyproject.toml` says it plainly: a bad verdict from a
  badly written I/O layer still gets caught by the gates, so exhaustive branch coverage on I/O buys
  much less.
- The corollary is the allocation above. **A wrong suggestion in an I/O layer is caught by the gates.
  A wrong suggestion inside the gates is caught by nothing**, because the gates are the thing doing
  the catching.

A plausible-looking off-by-one in `resolve_final_action` would not fail a test you would think to
write. It would quietly let a `TEST` action through where `HOLD` was required, and every downstream
claim would inherit the error while still looking well-formed.

### Specific traps in this codebase

| Trap | What a confident wrong suggestion looks like |
|---|---|
| Cost defaulting | `cost_ticks = payload.get("cost", 0)`. Zero is a *reported* value here, never a default. Use `CostMeasurement.unknown()`. |
| Retry loops | Wrapping `transport.invoke` in a retry. It is deliberately absent. Retries multiply spend exactly when you can least reason about it. |
| Replay fallback | `except FixtureMiss: return live_client.generate(...)`. This is the single most dangerous suggestion an assistant can make here. |
| Moderation retry | Rewording a prompt after a moderation rejection. That is evasion, and the rejection is terminal by design. |
| Evidence inflation | Changing `FROZEN_REPLAY` to something stronger so an action passes `IS8`. The gate is the point. |
| Gate short-circuit | Returning early from the gate chain "for performance". The chain is nine cheap pure functions. |

### Prompting Grok for the tiers where it is useful

Be specific about the boundary, and ask for the diff rather than the file:

```text
In hackathon/COST_LEDGER.md, rewrite section 6 so a non-engineer understands why cost per qualified
output is a legitimate claim and image-quality lift is not. Do not change any number. Do not touch
any other file. Use plain ASCII hyphens. Show only the changed lines.
```

### The runtime side: Grok Imagine as a dependency

Distinct from Grok as a coding assistant. Here the reliability question is about *outputs*, and the
architecture already answers it:

- Every output is validated before admission: `IS3` for provider completion and moderation, `IS4` for
  digest and dimensions.
- A moderation rejection is terminal and recorded.
- An ambiguous outcome raises `ProviderOutcomeUnknownError`, becomes an `UNKNOWN` result with unknown
  cost, and blocks further spending.
- Cost is whatever the provider reported, or an explicit unknown.

So the runtime posture is: **assume the provider can return something wrong or ambiguous, and make
that a typed state rather than an exception you hope nobody hits.** That is already implemented and
was verified end to end with zero network during the dry run.

## One-page summary

| Question | Answer |
|---|---|
| Where does the key live? | The environment. Never a file, never a chat, never workspace settings. |
| What can Grok write freely? | Prose, docs, slide copy, prompts, names. |
| What needs a human read? | Fixtures, demo surface, CLI, plotting, non-gate helpers. |
| What must Grok never write? | Gates, decisions, contracts, canonical hashing, receipts, mutations, ports, cost accounting. |
| Why that line? | The core is the checking layer. Nothing checks the checker. |
| What if Grok Imagine returns garbage at runtime? | `IS3` and `IS4` reject it, and unknown cost halts spending. |
