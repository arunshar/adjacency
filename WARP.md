# Warp rules for the Adjacency / ImagineSignal repository

**Read `hackathon/WARP_HANDOFF.md` in full before responding to anything.**

If this file is not auto-loaded by Warp, paste it in. Every rail below also appears in the handoff and
in `hackathon/WARP_BOOTSTRAP.txt`, so no single loading mechanism is load-bearing.

---

## The five hard rails

These lead this file on purpose. You have a terminal, so you can execute all of the things that must
not happen.

1. **Never commit, stage, push, tag, open a pull request, reset, clean, stash, or discard anything.**
   This worktree is intentionally dirty and uncommitted. Arun runs every git write himself. If a task
   seems to need one, stop and say so. `git status`, `git diff`, and `git log` are fine.
2. **Never make a live xAI or X Ads call.** Never read `XAI_API_KEY`, never set `ADJ_RECORD`, never
   run any command with `--write`. The one authorized probe is `hackathon/smoke_call.py`, and **Arun
   runs it, not you**.
3. **Never add retry or fallback to the Imagine transport, and never fall back from replay to live.**
   One invocation per call is a designed property. A missing fixture is terminal.
4. **Never record a cost of zero for an unreported provider cost.** Zero is a value the provider
   reports. An absent cost is `CostMeasurement.unknown()`, which deliberately blocks further calls.
5. **Plain ASCII hyphens only.** Never an em dash or an en dash, in code, comments, docs, or commit
   message drafts.

## Interpreter

**Use `python3.13`. Never bare `python3`.** The system interpreter is 3.14.6 and `pyproject.toml`
requires `>=3.12,<3.14`, so the default fails with `Package 'adjacency' requires a different Python`,
which reads like a broken repository rather than a wrong interpreter.

```bash
cd /Users/arunsharma/code/adjacency && python3.13 -m venv .venv && ./.venv/bin/pip install -qe ".[test,serve]"
```

The existing `.venv` is already correct. Only rebuild if it is missing.

## Verify before proposing any edit

```bash
cd /Users/arunsharma/code/adjacency && env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/pytest -m "not e2e" -q
```

```bash
cd /Users/arunsharma/code/adjacency && env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
```

```bash
cd /Users/arunsharma/code/adjacency && shasum -a 256 artifacts/imagine_signal/offline_demo.json
```

**And the lint gate, which CI runs and which is easy to forget:**

```bash
cd /Users/arunsharma/code/adjacency && .venv/bin/ruff check src tests scripts && .venv/bin/ruff format --check src tests scripts
```

CI runs exactly `ruff check src tests scripts` and `ruff format --check src tests scripts`. It does
**not** lint `slides/`, which has never been clean. If `ruff` is missing from the venv, install the
dev extra: `./.venv/bin/pip install -qe ".[dev]"`. Skipping this is how lint-breaking code reached
the branch on 2026-08-05.

Expected: suite green, status `verified`, and digest
`b17e9105f0de89772440c82938a69a7b25452784fc9c0667a4fe81a8f621ca73`. The suite count grows as work
lands, so treat the digest and the lint gate as the invariants, not the number.

**If the digest moves and you did not intend it, you changed decision logic. Do not regenerate to
make it match. Report the difference.**

After any task that edits files, also run:

```bash
cd /Users/arunsharma/code/adjacency && ./hackathon/verify_tree.sh
```

`git status --short` is **not sufficient in this repository**. It collapses an untracked directory
into one `??` line, and most of this project is untracked on purpose, so an edit inside
`src/adjacency/imagine_signal/` is invisible to it. `verify_tree.sh` compares file by file against
the last backup and exits non-zero if an undelegatable core file changed.

## Files you must not write

Nothing catches a mistake in these, because they are the thing that does the catching. Arun edits
them himself or they do not change.

```text
src/adjacency/imagine_signal/gates.py
src/adjacency/imagine_signal/decisions.py
src/adjacency/imagine_signal/contracts.py
src/adjacency/imagine_signal/canonical.py
src/adjacency/imagine_signal/receipts.py
src/adjacency/imagine_signal/mutations.py
src/adjacency/imagine_signal/ports.py
src/adjacency/gates.py
src/adjacency/contracts.py
the cost accounting in src/adjacency/imagine_signal/imagine_client.py
```

Everything else is delegatable, because the gates, the test suite, and the artifact digest catch
errors there. Full reasoning in `docs/imagine_signal/19_CURSOR_XAI_GROK.md`.

## Claims that must never appear

Evidence classes are `UNIT_TESTED`, `FROZEN_REPLAY`, and `SIMULATED`. Production is `NO_GO` and the
action ceiling is `TEST`.

Never write, in code, docs, comments, or UI text: live Grok image quality, image-quality lift,
advertiser lift, causal lift, production readiness, or X revenue of any kind.

## Where to look

| Need | File |
|---|---|
| Cold start | `hackathon/WARP_HANDOFF.md` |
| What to work on next | `hackathon/WARP_TASKS.md` |
| Saturday, brief is assigned that morning | `hackathon/CONTINGENCY.md` |
| Architecture and call-flow traces | `docs/imagine_signal/16_MASTER_EXPLAINER.md` |
| Every symbol | `docs/imagine_signal/17_API_REFERENCE.md` |
| xAI mechanics and cost | `hackathon/GROK_RUNBOOK.md` |
