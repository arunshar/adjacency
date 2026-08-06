# End-to-end dry run report

| Field | Value |
|---|---|
| Version | 1.0 |
| Run | 2026-08-05, America/Los_Angeles |
| Method | Full copy of the working tree into a scratch directory. `~/code/adjacency` was never modified. |
| Why a copy | The tree is intentionally uncommitted and `CLAUDE.md` forbids stash, reset, and clean. A real `git clone` would not carry untracked files, so a copy is the only faithful reproduction test. |
| Result | **11 of 11 stages ran. 8 clean, 3 surfaced real findings.** |

Everything below is actual output. Nothing is reconstructed from memory.

## Verdict

The offline path, the live code path, the canary push, and the demo UI all work. Three findings are
worth acting on before Saturday, and one of them is a genuine blocker for a teammate cloning the
repo. None of them affect the frozen evidence: the artifact digest is unchanged.

## Stage results

| # | Stage | Result |
|---:|---|---|
| 1 | Copy tree, git intact | PASS. 42 MB, `main` at `cd218dd`, same 4 modified + untracked set |
| 2 | Fresh virtual environment | **FINDING 1** on first attempt, PASS with the documented interpreter |
| 3 | Branch, stage, commit | PASS. 72 files, 17,644 insertions, commit `83599f4` |
| 4 | Full suite | PASS with **FINDING 2**. `446 passed, 1 skipped, 2 xfailed` |
| 5a | CI gate 1, deterministic core | PASS. `Required test coverage of 100% reached. Total coverage: 100.00%` |
| 5b | CI gate 2, package floor | PASS. `Required test coverage of 55% reached. Total coverage: 86.93%` |
| 6 | ruff check and format | **FINDING 3**. `No module named ruff` |
| 7 | Fixture verify, demo verify, digest | PASS. Digest matches exactly |
| 8 | Live code path, zero network | PASS. **17 of 17 checks** |
| 9 | Demo UI walkthrough | PASS, with the known no-ImagineSignal-UI gap confirmed |
| 10 | Canary push and rollback rehearsal | PASS. Clean in both directions |
| 11 | Deck rebuild | 3 of 4 scripts PASS, **FINDING 4** on the fourth |

---

## Finding 1: a fresh clone with default `python3` cannot install

```text
ERROR: Package 'adjacency' requires a different Python: 3.14.6 not in '<3.14,>=3.12'
```

The system `python3` on this machine is 3.14.6. `pyproject.toml` requires `>=3.12,<3.14`.

**The repository is not wrong.** `.python-version` says `3.13`, and `README.md:58` gives the correct
command. Rebuilding with `python3.13 -m venv .venv` installed cleanly, and the resulting environment
reported `gradio 6.22.0`, `pydantic 2.13.4`.

**The gap is mine.** `hackathon/CANARY_RELEASE.md` section 7 gives teammates a one-line clone command
that does not mention the interpreter. A teammate pasting it on Saturday morning gets a confusing
error at the worst possible moment.

**Action:** the clone command must be `python3.13`-explicit. Fixed in this pass.

## Finding 2: the expected test count depends on which extras are installed

| Environment | Result |
|---|---|
| Fully equipped (the working `.venv`) | `448 passed, 2 xfailed` |
| `pip install -e ".[test,serve]"` | `446 passed, 1 skipped, 2 xfailed` |

Cause: `temporalio` lives in the separate `temporal` extra, so `tests/test_temporal_hitl.py` skips at
module level, which suppresses its 2 tests and reports as 1 skip.

Package coverage moves for the same reason: **87.79%** fully equipped, **86.93%** without. Both are
far above the 55 percent floor.

**Action:** documented in [16_MASTER_EXPLAINER.md](16_MASTER_EXPLAINER.md) section 8 so nobody burns
twenty minutes on Saturday chasing two missing tests.

## Finding 3: `ruff` is not installable from `pyproject.toml`

`[tool.ruff]` and `[tool.ruff.lint]` configure it, `.pre-commit-config.yaml` pins
`ruff-pre-commit v0.9.0`, and the working `.venv` has `ruff 0.16.1` as a binary. But **no extra
declares it**, so a fresh clone following the README cannot run the lint gate directly.

Not a blocker, since pre-commit fetches its own. Worth knowing before someone reports "ruff is
broken" mid-build.

## Finding 4: `python-pptx` is undeclared entirely

```text
ModuleNotFoundError: No module named 'pptx'
```

`slides/build_pptx.py` imports it and no extra declares it. The other three deck scripts
(`build_deck.py`, `make_portable.py`, `build_pdf.py`) all ran clean.

**Also worth knowing:** `build_pptx.py` requires `slides_png/slide_NN.png` for **every** slide in
`_deck_data.json` and raises `FileNotFoundError` if one is missing. Adding slides therefore requires
re-rendering PNGs first. The correct order is:

```text
build_deck.py  ->  make_portable.py  ->  render_all.sh  ->  build_pptx.py  ->  build_pdf.py
```

Chrome is present at the path `render_all.sh` hard-codes, so the render step works on this machine.

## Stage 8 detail: the live code path, with zero network

The most valuable stage. A local fake transport drove the **real** `LiveImagineClient` through asset
validation, content addressing, and cost admission. The only substitution was the HTTP call itself.

```text
A. LIVE path, known cost
  [PASS] mode is LIVE                        [PASS] origin is LIVE_PROVIDER
  [PASS] state COMPLETED                     [PASS] one image admitted
  [PASS] media content-addressed             [PASS] bytes persisted to disk
  [PASS] cost exact  220000000 ticks = $0.022000
  [PASS] budget WITHIN_LIMIT                 [PASS] transport invoked exactly once
  [PASS] request digest recorded             [PASS] response digest recorded

B. unknown cost must halt spending
  [PASS] first call budget UNKNOWN
  [PASS] second call BLOCKED until reconciled
  [PASS] transport not invoked a second time

C. zero cost cap is refused at construction  [PASS]
D. unapproved policy is refused              [PASS]

LIVE PATH PROBE: ALL PASS
```

This is the strongest de-risking result in the run. On Saturday the only unwritten code is the HTTP
body and the field extraction. Everything downstream is proven.

## Stage 9 detail: the demo UI

`app.py` launched from the dry-run copy, served HTTP 200 in 3 seconds, and the Autopsy demo ran end
to end: the `GATE FAIL: G1_SPAN_NOT_FOUND` banner appeared, trace tables populated across AGREE,
OVER_BLOCK, and UNDER_BLOCK, and the illustrative recovered-spend counter moved from `$0.00` to
`$200.00`.

**Confirmed gap:** this is base Adjacency. There is no ImagineSignal surface. `ui.py` never imports
`imagine_signal`. The Autopsy demo is a working fallback, not an ImagineSignal demo.

## Stage 10 detail: canary push rehearsal

Run against a local bare repository, so nothing touched GitHub.

```text
branch push OK
tag created
tag push OK
remote: canary/imagine-signal, v0.3.0-canary
-- rollback --
tag delete OK
branch delete OK
remaining on remote: (empty)
```

The rollback in `hackathon/CANARY_RELEASE.md` section 8 is correct and leaves nothing behind.

## Real repository state after the run

```text
branch: main    head: cd218dd
unpushed commits: 0    stashes: 0
untracked (non-pycache): 68    modified: 4
```

Unchanged. The dry run touched nothing.

## Prioritized action list

| Priority | Item | Status |
|---|---|---|
| 1 | **Build an ImagineSignal demo surface**, time-boxed on Saturday | Scheduled in [18_HACKATHON_PUSH_STRATEGY.md](18_HACKATHON_PUSH_STRATEGY.md) |
| 2 | Make the teammate clone command `python3.13`-explicit | Fixed in this pass |
| 3 | Note the extras-dependent test count | Documented |
| 4 | Declare `ruff` and `python-pptx`, or note they are external | Noted, left to Arun's call |
| 5 | Remember the deck build order before adding slides | Documented above |

## Reproducing this

Every stage is a plain command. The scratch copy was deleted after the run. To repeat it, copy the
tree excluding `.venv`, `__pycache__`, and `.claude/worktrees`, build a venv with `python3.13`, and
run the stages in the order of the table at the top.
