# Warp cold-start handoff

**Status: the canary is released and green. Read this file in full before responding. Do not edit
anything until you have verified the checkpoint in section 6.**

| Field | Value |
|---|---|
| Version | **2.0** |
| Prepared | 2026-08-05, rewritten 2026-08-06 |
| Repository | `/Users/arunsharma/code/adjacency` |
| Branch | `canary/imagine-signal` at `94a1d27`, **clean and pushed** |
| Release | Tag `v0.3.0-canary` at `53ad8d4`, draft pull request #10, CI green on both jobs |
| Fallback | `main` stays at `cd218dd` and never moves during the event |
| Reason for handoff | Claude session limits. Warp is the primary agent for this project. |
| Event | xAI Grokathon, Saturday 2026-08-08, 09:00 to Sunday 01:00, San Francisco |

> **What changed from v1.0.** That version described a dirty, uncommitted tree on `main` with two
> unimplemented transport functions and a five-task queue. All of it shipped. The tree is clean, the
> branch is pushed and tagged, the transport is implemented on inline base64, the demo surface
> exists, and CI is green. If you are working from a v1.0 checkpoint you will halt on arrival for no
> reason. Section 6 below is authoritative.

## 1. What this is

**Adjacency** is a brand-safety policy engine. It compiles an advertiser's prose policy into a typed,
hashed, diffable `PolicySpec`, evaluates inventory, and reports the delta against a keyword blocklist
split into under-blocks and over-blocks. Its gates are `G0` through `G6`.

**ImagineSignal** extends the same discipline to creative generation. An advertiser has one approved
ad image. ImagineSignal builds a small family in which exactly one declared visual attribute changes,
with everything else locked and verified byte-identical, records lineage and real cost, and passes
every conclusion through gates `IS0` through `IS8` to a decision receipt. It is isolated under
`src/adjacency/imagine_signal/` and nothing in base Adjacency imports it.

The output is not an image. It is a decision receipt: keep, edit, test, hold, review, or stop, with
the evidence class that justified it attached.

## 2. How to behave

Warp agent mode, autonomous within the rails in section 3. Work in small verified steps: propose,
run the checks, report what actually happened. When explaining, go deep and use plain language with
concrete analogies rather than jargon.

State exactly what you verified and what you did not. Never present a number you did not produce by
running something. If a command fails, show the real error rather than summarizing it.

## 3. The five hard rails

Repeated verbatim from `WARP.md` so this file stands alone. They lead because you have a terminal and
can execute every one of the forbidden things.

1. **Never commit, stage, push, tag, open a pull request, reset, clean, stash, or discard.** Arun runs
   every git write. `git status`, `git diff`, `git log` are fine.
2. **Never make a live xAI or X Ads call.** Never read `XAI_API_KEY`, never set `ADJ_RECORD`, never
   pass `--write`. Arun runs `hackathon/smoke_call.py` himself.
3. **Never add retry or fallback to the transport, and never fall back from replay to live.**
4. **Never record a cost of zero for an unreported provider cost.**
5. **Plain ASCII hyphens only.** No em dashes, no en dashes, anywhere.

Plus: **`python3.13`, never bare `python3`.** System python is 3.14.6 and pyproject requires `<3.14`.

## 4. The honesty spine

This is the non-negotiable part. The product's entire claim is that it refuses to overclaim, so an
overclaim anywhere undoes the thesis more thoroughly than a missing feature would.

| Evidence class | Supports |
|---|---|
| `UNIT_TESTED` | Deterministic behavior proven by tests. Nothing about the world |
| `FROZEN_REPLAY` | The exact committed synthetic replay reproduces. Not that outputs are good |
| `SIMULATED` | A scenario result under stated assumptions. Nothing observed |

Production is `NO_GO`. The action ceiling is `TEST`, meaning propose a later authorized test only.

**Never claim**, in code, comments, documentation, commit-message drafts, or UI text: live Grok image
quality, image-quality lift, advertiser lift, causal lift, production readiness, or X revenue of any
kind.

The synthetic three-of-three versus two-of-three comparison in the offline artifact is a
fixture-backed pipeline check. It is not measured provider efficiency. If it appears anywhere, the
qualifier appears with it.

## 5. Where things are

```text
/Users/arunsharma/code/adjacency/
  WARP.md                          rails, read first
  CLAUDE.md                        the same rules, written for Claude
  src/adjacency/                   base engine, gates G0-G6
  src/adjacency/imagine_signal/    ImagineSignal, gates IS0-IS8, 15 modules
  tests/                           488 passing, no xfails
  hackathon/                       the event kit, see below
  docs/imagine_signal/             00 to 20, plus system_design.html and diagrams/
  slides/                          13-slide deck, build scripts, rendered PNGs
  artifacts/imagine_signal/        the frozen offline demo artifact
~/code/adjacency-backups/          timestamped backups, plus a verified git bundle of
                                   the canary branch, the tag, and main
~/code/adjacency-prep/             interview prep, deliberately outside the repo
```

The event kit in `hackathon/`:

| File | Purpose |
|---|---|
| `CONTINGENCY.md` | **Read this before Saturday.** The brief is assigned on the day |
| `GROK_RUNBOOK.md` | xAI mechanics, cost policy, failure playbook |
| `PREFLIGHT.md` | Friday account checks and the one authorized smoke call |
| `CANARY_RELEASE.md` | The push procedure, including the CI trap |
| `COST_LEDGER.md` | The UNVERIFIED provider field map, and the spend log |
| `WARP_TASKS.md` | **Your queue** |

The six deep-dive documents live in `docs/imagine_signal/`, numbered 15 through 20. Start with
[`16_MASTER_EXPLAINER.md`](../docs/imagine_signal/16_MASTER_EXPLAINER.md), which carries the module
map, the call-flow traces with real line anchors, and what may and may not be claimed.

### The Saturday decision, inlined so you do not need another file

The organizer confirmed the brief is shared the morning of the event, so **ImagineSignal is probably
not the submission**. At 09:00, read the brief and answer one question:

> Does the brief involve a model or agent producing an output that somebody has to trust?

| Answer | Move |
|---|---|
| **Yes** | Retarget the harness. `docs/RETARGETING.md` has the mechanical procedure, roughly 90 minutes |
| **Partly** | Build the product normally, drop gates and receipts into the one component that needs defending |
| **No** | **Start fresh. Do not force it.** Bolting a verification harness onto a brief that does not need one reads as "he had a hammer" and is worse than a clean small build |

Full version with the provider ladder in `CONTINGENCY.md`.

## 6. Verify this checkpoint before editing anything

```bash
cd /Users/arunsharma/code/adjacency && git branch --show-current && git rev-parse --short HEAD && git status --short | head
```

```bash
cd /Users/arunsharma/code/adjacency && env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/pytest -m "not e2e" -q
```

```bash
cd /Users/arunsharma/code/adjacency && env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only && shasum -a 256 artifacts/imagine_signal/offline_demo.json
```

| Expected | Value |
|---|---|
| Branch | `canary/imagine-signal` |
| HEAD | `94a1d27`, matching `origin/canary/imagine-signal` |
| Working tree | **clean**, `git status --short` prints nothing |
| Suite | `488 passed`, no xfails |
| Demo | `"status": "verified"`, `network_used: false` |
| Artifact digest | `b17e9105f0de89772440c82938a69a7b25452784fc9c0667a4fe81a8f621ca73` |
| `main` | still `cd218dd`, locally and on origin |
| `bandit -q -c pyproject.toml -r src` | exit 0 |

**If anything differs, report the exact difference and stop.** Do not repair it and do not regenerate
an artifact to make a digest match.

Two things that look wrong and are not. The tag `v0.3.0-canary` points at `53ad8d4`, one commit
behind `HEAD`, because the release was tagged before a documentation correction landed. And `main`
being three commits behind is the plan, not neglect: it is the known-good fallback.

Note: the suite reports fewer passes plus skips in an environment built from `.[test,serve]` alone,
because `temporalio` and `gradio` live in separate extras. The `core-without-model-deps` CI job
deliberately runs that way and reports `477 passed, 3 skipped`. Both are correct.

## 7. What is already done, so you do not redo it

- ImagineSignal offline MVP: 15 modules, 304 documented symbols, gates `IS0` to `IS8`, receipts,
  auction sensitivity, deterministic artifact.
- **The live transport is implemented**, at `src/adjacency/imagine_signal/adapters/xai_live.py`, using
  inline `response_format: "b64_json"`. That choice removed the entire URL-fetch and SSRF surface:
  no second host, no allowlist to maintain, no expiring link. `tests/hackathon/test_xai_live_contract.py`
  now carries **50 tests** and no xfails.
- **Nine live provider probes, $0.199 total.** Measured: generation $0.02 at 5.5s, edit $0.022 at
  9.2s, payload 122 to 208 KB, a 300-request budget, and policy compilation at $0.0368, which is
  dearer than an image. Full field map and spend log in `hackathon/COST_LEDGER.md`.
- **The demo surface exists.** `app.py` serves an ImagineSignal tab beside Autopsy, from 496 lines in
  `src/adjacency/imagine_signal/ui.py`, with 5 tests. It renders the family, the changed axis, the
  locked attributes, cost from the artifact, the `IS0` to `IS8` ladder, the final action, and an
  explicit list of claims it will not make.
- **The canary is released.** Branch pushed, tag pushed, draft pull request #10 open, CI green.
- Six deep-dive documents, five diagrams, two HTML walkthroughs, a 13-slide deck.
- A full dry run: fresh clone, branch, commit, both CI gates, canary push and rollback rehearsal, and
  a demo UI walkthrough. Findings in `docs/imagine_signal/20_DRY_RUN_REPORT.md`.

## 8. Your queue

`hackathon/WARP_TASKS.md` **version 2.0**. The v1.0 queue is finished. Two items remain: an optional
dead-code cleanup that is larger than it looks, and Saturday's assigned brief.

## 9. Do NOT

- Do not run any git write command. Not once, not "just to check".
- Do not make a live provider call or touch `XAI_API_KEY`.
- Do not edit any file in the undelegatable list in `WARP.md`.
- Do not weaken a gate, a contract, an evidence label, or a claim qualifier.
- Do not guess an xAI response field name. Every one now in the code was confirmed by a real probe,
  and the field map in `COST_LEDGER.md` records which. Keep that property.
- Do not regenerate a fixture or artifact to make a check pass.
- **Do not treat a green test suite as a green build.** `bandit` is a CI gate, it is not covered by
  the suite, and it is the only gate that has ever failed here. Run it.
- **Do not assume a branch push proved anything.** `ci.yml` triggers on `pull_request` and on `push`
  to `main` only, so a branch push runs zero checks. Pull request #9 failed on `bandit`, was closed
  within 76 seconds, and its branch was deleted, which removed the failure from the branch list, the
  pull request list, and `git ls-remote`. Only `gh run list --branch <name>` still showed it.
- Do not assume ImagineSignal is the Saturday submission. The brief is assigned that morning.
- Do not assume there is a scheduled interview. There is not. Recruiters will be onsite informally.

## 10. Your first move

1. Run the three checkpoint commands in section 6.
2. Read `hackathon/WARP_TASKS.md`.
3. Summarize back in about eight lines: what this project is, the checkpoint result, which rails
   constrain you, and which task you are taking first.
4. Then either start the task you named or ask one specific question. Do not ask for permission in
   general terms.
