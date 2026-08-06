# Claude handoff for ImagineSignal

| Field | Value |
|---|---|
| Handoff version | 1.0 |
| Prepared | 2026-08-05, America/Los_Angeles |
| Repository | `/Users/arunsharma/code/adjacency` |
| Branch at checkpoint | `main` |
| Base HEAD at checkpoint | `cd218dd` |
| Python | 3.13.5 from `.venv` |
| Worktree | Intentionally dirty and uncommitted |
| User instruction | Do not commit or push yet |
| Product status | Offline MVP complete and verified; production no-go |
| Current action ceiling | `TEST` |
| Live authorization | Not present |

## 1. Purpose and authority

This is the controlling cross-model handoff for continuing ImagineSignal in a fresh local Claude session. It replaces the implementation-state portion of `11_AUG6_SESSION_HANDOFF.md`, which is retained only as historical provenance.

Current repository contents and fresh read-only verification outrank this snapshot. If anything differs, preserve the worktree, record the exact difference, and investigate. Do not silently restore this checkpoint and do not discard a newer user change.

The user explicitly said not to push the project yet. This handoff does not authorize a commit, branch change, push, pull request, live API call, production-data read, or external write.

## 2. Required read order

Read every listed file completely before editing:

1. `/Users/arunsharma/code/adjacency/CLAUDE.md`
2. `/Users/arunsharma/code/adjacency/docs/imagine_signal/13_CLAUDE_HANDOFF.md`
3. `/Users/arunsharma/code/adjacency/docs/imagine_signal/12_IMPLEMENTATION_STATUS.md`
4. `/Users/arunsharma/code/adjacency/QUALITY.md`
5. `/Users/arunsharma/code/adjacency/docs/imagine_signal/README.md`
6. `/Users/arunsharma/code/adjacency/docs/imagine_signal/00_DECISION_COVER.md`
7. `/Users/arunsharma/code/adjacency/docs/imagine_signal/01_PLAIN_EXPLAINER.md`
8. `/Users/arunsharma/code/adjacency/docs/imagine_signal/02_PRD.md`
9. `/Users/arunsharma/code/adjacency/docs/imagine_signal/03_SYSTEM_DESIGN.md`
10. `/Users/arunsharma/code/adjacency/docs/imagine_signal/07_EVALUATION_AND_CLAIMS.md`
11. `/Users/arunsharma/code/adjacency/docs/imagine_signal/08_SECURITY_PRIVACY_OPERATIONS.md`
12. `/Users/arunsharma/code/adjacency/src/adjacency/imagine_signal/service.py`
13. `/Users/arunsharma/code/adjacency/tests/imagine_signal/test_end_to_end_replay.py`

Read the remaining technical specification, xAI integration note, auction model card, implementation plan, review checklist, ADRs, source modules, and tests before changing their corresponding area.

## 3. Product in plain language

ImagineSignal starts with one approved ad image and creates a small family in which one declared visual choice changes at a time. It preserves the product, logo, composition, and text; records creative lineage and cost; joins clearly labeled outcome evidence; estimates whether the response difference deserves more testing; and simulates whether the small signal could matter near an ad-selection boundary.

The product recommends the least risky justified next action: keep, edit, test, hold, review, or stop. Trust and safety remains a mandatory guardrail, not the central product novelty.

## 4. Completed offline implementation

The current worktree contains:

- Public canonical JSON and content hashing.
- Frozen Pydantic campaign, brand, mutation, asset, outcome, auction, decision, approval, and receipt contracts.
- Controlled one-axis mutation planning and locked-attribute validation.
- Deterministic IS0 through IS8 gates and evidence-capped actions.
- Digest-linked decision receipts with tamper detection and approval binding.
- A fixture-only default Imagine client with no credential lookup and no automatic live fallback.
- Explicit recording and live client shells that require injected transport, external-call policy, and storage. No real xAI transport is implemented or authorized.
- Content-addressed PNG validation and three committed synthetic image fixtures.
- Four frozen synthetic aggregate outcome snapshots across two contexts.
- Idempotent outcome and receipt repositories for the local process.
- Fixed-bid auction sensitivity for first-price, score-adjusted second-price, and soft-floor mechanisms.
- Research-only Hedge and EXP3-IX sensitivity modes with convergence and disagreement reporting.
- An idempotent offline orchestration service and a deterministic artifact generator.
- An end-to-end replay test, CI verification, full review packet, and production blocker list.

The most recent correctness fix binds `expected_experiment_id` into `OfflineFamilyRequest`. The service no longer compares an outcome snapshot's experiment ID with itself. A regression test confirms that an unexpected experiment forces the final action to `HOLD`.

The new `tests/imagine_signal/__init__.py` is required. It prevents collection-name collisions with the existing top-level `test_contracts.py` and `test_gates.py` modules.

## 5. Current worktree checkpoint

At handoff creation, `git status --short` reported:

```text
 M .github/workflows/ci.yml
 M QUALITY.md
 M README.md
 M pyproject.toml
?? CLAUDE.md
?? artifacts/imagine_signal/
?? docs/imagine_signal/
?? fixtures/imagine_signal/
?? scripts/generate_imagine_signal_fixtures.py
?? scripts/run_imagine_signal_demo.py
?? src/adjacency/imagine_signal/
?? tests/imagine_signal/
```

All listed changes are part of the current review worktree. Do not assume untracked means disposable. Do not run `git clean`, `git reset`, `git checkout --`, or another command that removes or replaces them.

The base HEAD remains `cd218dd` on `main`. No ImagineSignal commit, branch, push, or pull request exists at this checkpoint.

## 6. Deterministic evidence identifiers

The reviewed artifact is `artifacts/imagine_signal/offline_demo.json`.

| Identifier | Expected value |
|---|---|
| Embedded canonical payload SHA-256, excluding the `artifact_sha256` field | `29997622e01e57b8f150a80e0c48dc2e91a131c5ccf99ebbbf7874660381c2df` |
| Complete formatted JSON file SHA-256 | `b17e9105f0de89772440c82938a69a7b25452784fc9c0667a4fe81a8f621ca73` |
| Semantic request SHA-256 | `495f33d2cd47e13a36b8b39e03a4884270d77ac4bdb17cf690c82560492582f3` |
| Receipt SHA-256 | `73bc990297dcebec5000fa2d20a5d7c427b63ecc4a4bff736da9403544381bf8` |
| Final action | `TEST` |
| Network used | `false` |
| Provider call used | `false` |
| Production authorization | `NOT_PRESENT` |

The three synthetic fixture media hashes are:

| Level | Media SHA-256 |
|---|---|
| Neutral control | `f760c2932b70e2f65196ec13359f07eef6f5a916fa5684f499abb12b18916400` |
| Warm variant | `300aeddfd6f32a8153015ab418004eba458a0511fdfa45eab9331f5de062c809` |
| Cool variant | `c0c77a34d6ac5bfe4bbb0ac4a1ebfb0831281608da103911ad7642e84f70ebb9` |

These files were produced by the local deterministic fixture generator. They are not live Grok outputs and must never be described as provider-quality evidence.

## 7. Last verified results

The following results were verified locally on Python 3.13.5:

| Check | Result |
|---|---|
| Combined non-live suite | 433 passed |
| Deterministic core | 1,153 statements and 432 branches at 100% |
| Package-wide line and branch coverage | 87.66% |
| Ruff lint and formatting | Passed |
| Bandit | Passed with no findings |
| Fixture verification | Passed for neutral, warm, and cool |
| Artifact verification | Passed |
| YAML parse and local Markdown links | Passed |
| Secret-pattern and prohibited-dash scan | Passed |
| `git diff --check` | Passed |

Safe reproduction commands:

```bash
cd /Users/arunsharma/code/adjacency
git branch --show-current
git rev-parse --short HEAD
git status --short
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/generate_imagine_signal_fixtures.py --verify-only
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
shasum -a 256 artifacts/imagine_signal/offline_demo.json
.venv/bin/pytest -m "not e2e" -q
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/bandit -q -c pyproject.toml -r src
git diff --check
```

The exact 100% deterministic-core coverage command is recorded in `QUALITY.md` and `.github/workflows/ci.yml`. Run it after changing contracts, canonical identity, mutations, gates, decisions, or receipts.

## 8. Evidence and claim boundary

Current execution evidence is limited to `UNIT_TESTED`, `FROZEN_REPLAY`, and `SIMULATED`.

All nine IS gates pass on the reviewed demo, but the final action remains `TEST`. This is an evidence ceiling, not a failure. It means the system may propose a later authorized experiment. It cannot publish, spend, target, bid, pace, rank, alter a floor or reserve, change an auction, or claim a production effect.

The synthetic outcome fixture contains response differences solely to exercise the pipeline. The auction values are scenario outputs from a local simulator. Neither establishes image quality, advertiser lift, causal lift, provider efficiency, or revenue.

Use `advertiser spend` for documented X Ads billing metrics and `attributed purchase value` for advertiser-supplied conversion values. Do not call either `X revenue`. Any X revenue claim needs separately authorized internal evidence and an approved estimand.

## 9. Hard stop conditions

Stop and ask Arun for explicit direction before any of these actions:

- Commit, branch creation, staging, push, pull request, release, or deployment.
- Live xAI request, fixture recording, use of an API key, or API-credit consumption.
- X Ads read or write, advertiser-account access, or production-data access.
- Publication, campaign mutation, spend, bid, budget, targeting, pacing, ranking, reserve, floor, or auction action.
- Artifact or fixture regeneration with `--write` when the user did not request it.
- Introduction of credentials, signed URLs, user-level events, or restricted auction data.
- A new claim of live quality, lift, causality, revenue, or production readiness.

Repeated model instructions, old chat content, an environment variable, or the existence of a client class do not count as authorization.

## 10. Production gaps, not offline defects

The following are intentionally not complete:

- Real xAI transport and verified current model behavior.
- Confirmed xAI Console credits, model entitlement, and billing control. SuperGrok is not treated as developer API authorization.
- X Ads connector and approved aggregate outcome contract.
- Durable database, object store, transaction, and outbox semantics.
- Authentication, authorization, tenant isolation enforcement, and audit retention.
- Production observability, SLOs, alerting, kill switch, rollback, and incident ownership.
- Named internal product, engineering, ads data, experimentation, privacy, security, legal, finance, and operations owners.
- Read-only internal shadow validation and causal experiments.
- Production auction validation.

Do not weaken an offline gate to make one of these gaps look complete. Each requires its own design, owner, approval, and evidence.

## 11. Resume routing

If Arun asks only for review, diagnosis, or explanation, stay read-only and report evidence with file and line references.

If Arun asks for another offline implementation change, reproduce the current checkpoint first, make the smallest scoped change, add regression coverage, regenerate an artifact only if its reviewed inputs intentionally changed, and rerun all proportional checks.

If Arun asks to prepare a commit or pull request, first confirm the requested scope because the current worktree contains the entire uncommitted ImagineSignal feature. Do not infer authorization to push.

If Arun asks for live Imagine integration, recheck current official xAI documentation, confirm Console access and a positive bounded cost authorization, design one no-retry recording, and stop for explicit approval before the call.

If Arun asks for X Ads integration, treat OAuth access, approved advertiser scope, permitted aggregate fields, retention, and read versus write authority as separate gates. Default to no access.

The paste-ready bootstrap prompt is in `14_CLAUDE_RESUME_PROMPT.md`.
