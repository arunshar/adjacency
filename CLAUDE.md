# Claude instructions for Adjacency and ImagineSignal

This repository is in an intentionally dirty, uncommitted review state. Do not commit, push, open a pull request, discard, reset, clean, stash, or overwrite any current change unless Arun explicitly asks for that exact action.

## Mandatory startup

Before changing anything, read these files completely in this order:

1. `docs/imagine_signal/13_CLAUDE_HANDOFF.md`
2. `docs/imagine_signal/12_IMPLEMENTATION_STATUS.md`
3. `QUALITY.md`
4. `docs/imagine_signal/README.md`
5. `docs/imagine_signal/00_DECISION_COVER.md`
6. `docs/imagine_signal/07_EVALUATION_AND_CLAIMS.md`
7. `docs/imagine_signal/08_SECURITY_PRIVACY_OPERATIONS.md`

Then inspect the current branch, HEAD, worktree, and artifact before relying on any recorded status. The repository is authoritative if this file, an older handoff, model memory, or chat history disagrees with current files and verification output.

## Current controlling boundary

ImagineSignal is complete only as a local offline MVP backed by unit tests, frozen synthetic replay, and explicit auction simulation. Production remains a no-go.

Do not make a live xAI or X Ads call. Do not use `XAI_API_KEY`, enable `ADJ_RECORD`, publish an ad, change spend, change bids, change targeting, export a ranking signal, or modify an auction. No current file authorizes any external call or production-data access.

A missing fixture is terminal. Never fall back from replay to a live provider. An artifact mismatch requires investigation before regeneration. Do not run an artifact or fixture command with `--write` unless the user explicitly requests an intentional regeneration after the relevant change has been reviewed.

## Evidence and claim rules

Keep every statement within its evidence class:

- `UNIT_TESTED` supports tested deterministic behavior only.
- `FROZEN_REPLAY` supports the exact committed synthetic replay only.
- `SIMULATED` supports scenario-conditional auction statements only.
- The current final action is `TEST`, meaning propose a later authorized test only.

Do not claim live Grok Imagine quality, image-quality lift, advertiser lift, causal lift, production readiness, or X revenue. Public X Ads analytics may support advertiser spend or attributed purchase value when configured. X revenue requires separately authorized internal evidence.

## Editing conventions

- Preserve the existing Adjacency contracts, actions, and G0 through G6 semantics.
- Keep ImagineSignal isolated under `src/adjacency/imagine_signal/` with IS0 through IS8.
- Preserve all current user and model changes. Work around unrelated edits.
- Use plain ASCII hyphens. Never use em dash or en dash characters.
- Keep code and documents free of credentials, signed URLs, raw authorization headers, and user-level advertising data.
- Update tests, deterministic artifacts, documentation, and CI together when a contract changes.
- State exactly what was verified. Never invent or extrapolate a metric.

## Safe first commands

Run these from `/Users/arunsharma/code/adjacency` before implementation work:

```bash
git branch --show-current
git rev-parse --short HEAD
git status --short
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/generate_imagine_signal_fixtures.py --verify-only
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
shasum -a 256 artifacts/imagine_signal/offline_demo.json
.venv/bin/pytest -m "not e2e" -q
```

If any result differs from the checkpoint in `docs/imagine_signal/13_CLAUDE_HANDOFF.md`, report the exact difference before editing. The detailed continuation prompt is in `docs/imagine_signal/14_CLAUDE_RESUME_PROMPT.md`.
