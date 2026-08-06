# Grok runbook for the hackathon

| Field | Value |
|---|---|
| Version | 1.0 |
| Prepared | 2026-08-05 |
| Event | xAI Grokathon, San Francisco, Sat 2026-08-08, 09:00 to Sun 01:00 |
| Repository | `/Users/arunsharma/code/adjacency` |
| Base at preparation | `main` at `cd218dd`, plus the uncommitted ImagineSignal worktree |
| Read time | About six minutes |

> **READ [CONTINGENCY.md](CONTINGENCY.md) FIRST.** The organizer confirmed on 2026-08-05 that the
> brief is assigned on the morning of the event and that no provider details are being given in
> advance. **ImagineSignal is probably not the submission.** This runbook still governs the Grok and
> xAI mechanics, but the 09:00 decision about what to build lives in the contingency plan.

**After that, if you read one more file, read this one.** Everything else is reference.

## 1. What ImagineSignal does

An advertiser has one approved ad image. ImagineSignal creates a small family of
variants in which exactly one declared visual choice changes at a time, keeping
product, logo, composition, and text locked. It records creative lineage and
cost, joins clearly labeled outcome evidence, estimates whether a response
difference deserves more testing, and simulates whether that small signal could
matter near an ad-selection boundary. It then recommends the least risky
justified next action: keep, edit, test, hold, review, or stop.

The point is not "generate more images faster." The point is qualified evidence
per generation dollar, with a receipt for every claim.

## 2. The one seam

The entire live integration is one class with one method.

```text
ports.ImagineTransport (Protocol)
    invoke(*, operation, request) -> TransportResult
```

Everything downstream already exists and is tested: canonical hashing, PNG
validation, gates `IS0` through `IS8`, decision receipts, cost admission, and the
budget interlock. None of it changes when you go live.

The skeleton is at `src/adjacency/imagine_signal/adapters/xai_live.py`. The
executable contract is at `tests/hackathon/test_xai_live_contract.py`.

## 3. Rules that do not bend

These are enforced by code, not by discipline. Do not route around them.

1. **Replay is the default and needs no credential.** A missing fixture is
   terminal. There is no automatic fallback from replay to a live call. If you
   find yourself adding one, stop.
2. **An external call requires an approved `ExternalCallPolicy`.** It carries
   `approved`, `max_calls`, `max_outputs_per_call`, and `max_total_cost_ticks`.
   A zero cost cap is rejected at construction.
3. **Unknown cost blocks the next call.** If the provider does not report
   `usage.cost_in_usd_ticks`, the client records an explicit unknown and refuses
   further external calls until it is reconciled. It never records zero spend.
   This is what protects an unattended loop at 2 AM.
4. **A moderation rejection is terminal for that output.** Do not retry
   alternative wording to evade it.
5. **One invocation per call. No retry, no fallback.** A failure is a fact to
   report, not a condition to paper over.
6. **No credential, signed URL, raw authorization header, or base64 blob** goes
   into a log, fixture, artifact, commit, or screenshot.

## 4. Implementing the live transport

Two functions in `adapters/xai_live.py` raise `NotImplementedError` today. Both
have a full specification in their docstring, and both have a waiting test.

### Step 1: `extract_provider_response(raw, *, latency_ms)`

This is the only function that needs real xAI field names. Nothing in the
repository guesses them.

1. Make the first authorized call (see `smoke_call.py`).
2. Capture the raw response.
3. Fill in the extraction, in this order: moderation rejection first, then
   `usage.cost_in_usd_ticks`, then image bytes, then
   `provider_request_id` / `provider_model_resolved` / `moderation_respected`.
4. Record the confirmed field names in `COST_LEDGER.md` so the mapping is
   auditable afterwards.

Image bytes come from either base64 output, which you decode immediately, or a
temporary URL, which you fetch immediately from an allowlisted xAI host under
strict size, type, redirect, and timeout controls. Default generation URLs
expire. Never persist only the URL.

### Step 2: `XAIImagineTransport.invoke(...)`

```text
url     = endpoint_for(operation, base=self.base_url)
body    = build_request_body(request)     # lift _unverified once names are confirmed
raw     = self.http(method="POST", url=url, json_body=body)   # exactly once
payload = extract_provider_response(raw, latency_ms=elapsed_ms)
return    map_provider_response(payload)
```

If the request was sent but the outcome cannot be reconciled, raise
`ProviderOutcomeUnknownError(msg, provider_request_id=...)`. The bounded client
turns that into an `UNKNOWN` result with unknown cost and blocks further calls.

### Step 3: delete the xfail markers

`tests/hackathon/test_xai_live_contract.py` has two tests marked
`xfail(strict=True)`. While the functions are unimplemented they report as
expected failures and CI stays green. Once you implement correctly they XPASS,
and strict mode turns that into a failure on purpose. Delete the marker, replace
the placeholder raw response with the real recorded one, and the test becomes a
genuine regression test.

## 5. Cost control

Verified 2026-08-05 from `docs/imagine_signal/05_XAI_INTEGRATION.md`. Refresh
before budgeting.

| Model | Use | 1K output | 2K output | Rate limit |
|---|---|---:|---:|---:|
| `grok-imagine-image` | Broad exploration | $0.02 | $0.02 | 5 rps |
| `grok-imagine-image-quality` | Finalists only | $0.05 | $0.07 | 5 rps |

Cost unit: 10,000,000,000 ticks equal one US dollar. Use
`usd_to_ticks(0.50)` to build a cap rather than typing the integer by hand. The
helper floors, so a cap is never silently raised.

Spend policy for the day:

1. Validate the brief and locked constraints before any paid call.
2. Check for an existing replay fixture before generating.
3. Explore on the standard model. Promote only qualified candidates to quality.
4. Reject corrupt, moderation-failed, or duplicate outputs before spending more.
5. Batch same-prompt samples with `n` only within one mutation level.
6. Log every actual cost in `COST_LEDGER.md`. Not the estimate. The reported one.
7. Stop a family when the evidence says another generation is not justified.

## 6. Saturday shape

The build window is 09:00 to 01:00. This is a plan, not a schedule to defend.

| Block | Goal | Done means |
|---|---|---|
| 09:00 to 10:00 | Preflight and canary push | `PREFLIGHT.md` complete, branch and tag pushed, teammates cloned |
| 10:00 to 11:30 | First authorized call | One capped call recorded, field names confirmed, `extract` implemented |
| 11:30 to 13:00 | Transport complete | Both xfail markers deleted, full suite green |
| 13:00 to 15:00 | Live family | One real controlled family generated end to end with a receipt |
| 15:00 to 17:00 | Theme alignment | Whatever the announced theme requires, built on the existing gates |
| 17:00 to 19:00 | Demo path | Three-minute walk rehearsed twice, offline fallback verified |
| 19:00 to 21:00 | Hardening | Failure playbook exercised, cost ledger reconciled |
| 21:00 onward | Freeze and submit | Tag, artifact digests recorded, no new features |

Hard rule: **freeze features at 21:00.** A working demo at 21:00 beats a broken
better one at midnight. The offline replay demo already works and is your floor.

## 7. Commands

Verification, from the repository root. These are read-only and need no key.

```bash
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/generate_imagine_signal_fixtures.py --verify-only
```

```bash
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python -I -B scripts/run_imagine_signal_demo.py --verify-only
```

```bash
env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/pytest -m "not e2e" -q
```

Expected as of 2026-08-05: **448 passed, 2 xfailed**. The two xfails are the
live transport spec and are expected until Saturday.

Offline demo artifact digest:

```bash
shasum -a 256 artifacts/imagine_signal/offline_demo.json
```

Expected `b17e9105f0de89772440c82938a69a7b25452784fc9c0667a4fe81a8f621ca73`.

## 8. What you may and may not say

Evidence classes are load-bearing. A judge who catches an overclaim discounts
everything else you said.

| You may say | You may not say |
|---|---|
| Deterministic behavior is unit tested | Grok Imagine produces better images |
| The frozen replay reproduces exactly | Measured image-quality lift |
| The auction result is an explicit simulation | Revenue impact, or X revenue of any kind |
| One declared attribute changed, and we can prove it | Causal advertiser lift |
| Cost per qualified output is recorded per call | Production readiness |

Public X Ads analytics can support "advertiser spend" or "attributed purchase
value" when the advertiser configured them. Neither is platform revenue. The
current MVP has no X Ads dependency at all.

## 9. Failure playbook

| Symptom | Do this |
|---|---|
| Fixture miss | Stop. Do not add a live fallback. Regenerate the fixture deliberately or fix the request. |
| Unknown cost, calls blocked | Read the provider dashboard, reconcile actual spend, record it in the ledger, then explicitly reset the client. |
| Moderation rejection | Record it and move on. Do not reword to evade. |
| Rate limited | You are above 5 rps. Reduce concurrency. Do not add a retry loop. |
| No API credit | Continue entirely in fixture mode. The offline demo is a complete story on its own. |
| Everything is on fire at 22:00 | `git checkout` the frozen tag, run the offline demo, present that. It works and it is honest. |

## 10. Where to go deeper

- Product story for a non-engineer: `docs/imagine_signal/01_PLAIN_EXPLAINER.md`
- Exact completed boundary: `docs/imagine_signal/12_IMPLEMENTATION_STATUS.md`
- Provider surface and prices: `docs/imagine_signal/05_XAI_INTEGRATION.md`
- Claim rules: `docs/imagine_signal/07_EVALUATION_AND_CLAIMS.md`
- Account checks before Saturday: `hackathon/PREFLIGHT.md`
- Push procedure: `hackathon/CANARY_RELEASE.md`
- Running the build from Warp: `hackathon/WARP_HANDOFF.md`, queue in `hackathon/WARP_TASKS.md`,
  paste-in prompt in `hackathon/WARP_BOOTSTRAP.txt`
- Running it from Cursor, and the model risk tiers: `docs/imagine_signal/19_CURSOR_XAI_GROK.md`
