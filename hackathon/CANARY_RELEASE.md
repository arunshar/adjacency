# Canary release procedure

| Field | Value |
|---|---|
| Version | 1.0 |
| Prepared | 2026-08-05 |
| Strategy | Branch plus pre-release tag. `main` stays at `cd218dd`. |
| Branch | `canary/imagine-signal` |
| Tag | `v0.3.0-canary` |
| Rollback | Delete the branch and the tag. `main` is never touched. |

## 1. Why this shape

`main` currently sits at `cd218dd`, the frozen Grokathon paper and release kit.
That commit is a known-good demo you can fall back to at any hour of Saturday
night. Putting ImagineSignal on a separate branch keeps that property. Rollback
is a branch delete rather than a revert, and the frozen release point stays the
tip of `main`.

## 2. The trap: CI does not run on this branch

`.github/workflows/ci.yml` triggers only on `pull_request` and on `push` to
`main`. **Pushing `canary/imagine-signal` alone runs no checks at all.** You get
a green-looking branch with zero verification behind it.

The fix is one extra step: open a **draft** pull request from the canary branch
into `main`. That triggers the full CI matrix, gives teammates a review surface,
and merges nothing. Leave it draft for the whole event.

## 3. Verify before you push

Run all of it. Expected results are stated so a difference is obvious.

```bash
cd /Users/arunsharma/code/adjacency && git status --short
```

```bash
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/pytest -m "not e2e" -q
```

Expect `448 passed, 2 xfailed`. The two xfails are the live transport spec.

```bash
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
```

```bash
shasum -a 256 artifacts/imagine_signal/offline_demo.json
```

Expect `b17e9105f0de89772440c82938a69a7b25452784fc9c0667a4fe81a8f621ca73`.

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## 4. Secret scan before the first public push

The repository is about to become visible. Check once, deliberately.

```bash
git ls-files --others --exclude-standard -z | xargs -0 grep -lEi 'xai-[a-z0-9]{20,}|Bearer [A-Za-z0-9._-]{20,}|api[_-]?key["'"'"']?\s*[:=]' 2>/dev/null || echo "no credential-shaped strings found"
```

Also confirm `.env`, `.venv`, and any local key file are ignored:

```bash
git check-ignore -v .env .venv 2>/dev/null || echo "CHECK: .env or .venv is NOT ignored"
```

## 5. Push

```bash
cd /Users/arunsharma/code/adjacency && git switch -c canary/imagine-signal
```

```bash
git add -A && git status --short
```

Read that list before committing. It should be the 60 ImagineSignal files, the
4 modified tracked files, and the `hackathon/` kit. Nothing else.

```bash
git commit -m "Add ImagineSignal offline MVP and the Grokathon live-transport seam

Offline MVP only. Evidence is UNIT_TESTED, FROZEN_REPLAY, and SIMULATED.
No live xAI call, no X Ads read, no publish, no spend. Production is NO_GO
and the action ceiling is TEST. The live transport is a skeleton with an
executable contract and two strict-xfail specs."
```

```bash
git push -u origin canary/imagine-signal
```

```bash
gh pr create --draft --base main --head canary/imagine-signal --title "Canary: ImagineSignal offline MVP" --body "Draft on purpose. Do not merge during the event. Opened to run CI against the canary branch, which push alone does not do. Offline MVP only: no live call, no spend, production NO_GO."
```

## 6. Tag and pre-release

Only after the draft PR shows CI green.

```bash
git tag -a v0.3.0-canary -m "ImagineSignal offline MVP canary. Not production. Action ceiling TEST."
```

```bash
git push origin v0.3.0-canary
```

```bash
gh release create v0.3.0-canary --prerelease --target canary/imagine-signal --title "v0.3.0-canary ImagineSignal offline MVP" --notes "Canary pre-release for the xAI Grokathon. Offline MVP backed by unit tests, frozen synthetic replay, and explicit auction simulation. No live xAI call, no X Ads data, no publish, no spend. Production NO_GO, action ceiling TEST. Frozen paper and demo remain on main at cd218dd."
```

## 7. Teammate onboarding

One message, one command:

```bash
git clone -b canary/imagine-signal https://github.com/arunshar/adjacency.git && cd adjacency && python3.13 -m venv .venv && ./.venv/bin/pip install -qe ".[test,serve]" && cat hackathon/GROK_RUNBOOK.md
```

**`python3.13` is not optional.** `pyproject.toml` requires `>=3.12,<3.14`. A machine whose default
`python3` is 3.14 fails with `Package 'adjacency' requires a different Python`, which reads like a
broken repository rather than a wrong interpreter. This was caught in the dry run, see
[20_DRY_RUN_REPORT.md](../docs/imagine_signal/20_DRY_RUN_REPORT.md) finding 1.

Expected from that environment: `446 passed, 1 skipped, 2 xfailed`. The skip is
`tests/test_temporal_hitl.py`, because `temporalio` is in a separate extra. A fully equipped
environment reports `448 passed, 2 xfailed`. Both are correct.

## 8. Rollback

Nothing here touches `main`, so rollback is deletion.

```bash
gh release delete v0.3.0-canary --yes && git push origin :refs/tags/v0.3.0-canary && git push origin --delete canary/imagine-signal
```

## 9. During the event

Keep pushing to `canary/imagine-signal`. The draft PR re-runs CI on every push,
which gives you a free continuous check while you build. Cut a second tag
(`v0.3.1-canary`, and so on) at each stable point so there is always a recent
known-good commit to demo from.

At the 21:00 feature freeze, cut the final tag and stop.
