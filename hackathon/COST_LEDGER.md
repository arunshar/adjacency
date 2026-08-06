# Cost ledger and provider field map

| Field | Value |
|---|---|
| Version | 1.0 |
| Prepared | 2026-08-05 |
| Purpose | Record what the provider actually returned and actually charged |
| Rule | Log the reported cost, never the estimated one |

Two jobs. The first table unblocks `extract_provider_response`. The second keeps
spending honest and gives you a real number to quote in the interview.

## 1. VERIFIED provider field map

Settled 2026-08-05 by two authorized `smoke_call.py` probes against
`POST https://api.x.ai/v1/images/generations`, model `grok-imagine-image`, `n=1`. Total cost $0.04.

| What we need | Where it actually is | Status |
|---|---|---|
| Cost in ticks | `usage.cost_in_usd_ticks` | **CONFIRMED.** `200000000` = $0.020000, matching the published standard 1K price |
| Images array | `data` (list) | **CONFIRMED** |
| Image location | `data[0].url` | **CONFIRMED.** A URL, not base64. 93 characters. Temporary. Host is `imgen.x.ai` (verified 2026-08-06 diagnose-generate; not `api.x.ai`) |
| Media type | `data[0].mime_type` | **CONFIRMED.** `image/jpeg`, not PNG |
| Provider request id | `x-request-id` **response header** | **CONFIRMED.** Not in the body |
| Server-side latency | `x-metrics-e2e-ms` header | **CONFIRMED.** `5312.4`. More accurate than client timing |
| Resolved model | **NOWHERE** | **ABSENT** from the body and from all 20 response headers |
| Moderation disposition | **NOWHERE** | **ABSENT** from the body and from all 20 response headers |
| Output width and height | not returned | Read them from the decoded image bytes |

Full body shape:

```json
{"data": [{"url": "<93 chars>", "mime_type": "image/jpeg"}],
 "usage": {"cost_in_usd_ticks": 200000000}}
```

### The two absent fields, and the decisions taken

`_validate_transport_result` requires `provider_model_resolved` and `moderation_respected` on any
`COMPLETED` call. Neither exists in the response. That is the contract working, not a bug: the
requested-versus-resolved split exists precisely to catch a provider silently substituting a model,
and `grok-imagine-image` is a **moving alias**.

1. **Resolved model: use a dated alias in every request.** `grok-imagine-image-2026-03-02` rather
   than the moving alias. A dated alias cannot silently substitute, so setting
   `provider_model_resolved` from the requested model is then honest rather than a fiction. The cost
   is losing automatic model upgrades, which is the correct trade for reproducible evaluation.
   **Do not** set resolved from a moving alias. That destroys the check while appearing to satisfy it.
2. **Moderation: `True` only on `COMPLETED`.** A completed response carrying an image means
   moderation ran and did not reject. It must stay forbidden as `None` on every other state, and a
   moderation rejection must still map to `MODERATION_REJECTED` with an error code.

Both decisions are inferences rather than provider-reported facts, which is why they are recorded
here rather than buried in code.

### Other findings from the headers

| Header | Value | Why it matters |
|---|---|---|
| `x-zero-data-retention` | `false` | **xAI retains request data.** Send only synthetic or non-sensitive prompts and assets |
| `x-data-retention` | `general` | Confirms the fixture policy in `05_XAI_INTEGRATION.md` section 9 was right |
| `x-ratelimit-limit-requests` | `300` | A request-count budget alongside the documented 5 rps burst limit |
| `x-ratelimit-remaining-requests` | `300` | Unchanged after the call, so the window is generous |

### The edits endpoint, probed 2026-08-05

`POST /v1/images/edits` **works**, and the response is **shape-identical to generations**.

| Finding | Value |
|---|---|
| Request shape that worked | JSON body, `image.url` = a `data:image/png;base64,...` URI |
| Response body | Identical: `data[0].url`, `data[0].mime_type` (`image/jpeg`), `usage.cost_in_usd_ticks` |
| Cost | **220,000,000 ticks = $0.022**, exactly the documented $0.002 input plus $0.02 output |
| Latency | **9,352 ms client, 9,192.9 ms server.** About 1.75x a plain generation |
| Headers | Same set. Still no resolved model, still no moderation disposition |

**Consequence 1, good:** `extract_provider_response` needs **no change** for edits. The mapper
already handles this shape.

**Consequence 2, a real gap:** `build_request_body` currently emits `reference_media_sha256` and
`reference_file_ids` for an edit. **That is not what the API accepts.** It wants the bytes, as a
data URI.

`ImageReference` deliberately carries identity only: `media_sha256`, `media_type`, dimensions, and an
optional `provider_file_id`. No bytes. That separation is correct, because receipts must reference
digests rather than blobs. But the transport needs bytes at the boundary.

**The fix:** inject `ContentAddressedAssetStore` into `XAIImagineTransport` and resolve bytes at the
last moment with `read_verified(descriptor)`. Contracts keep carrying identity, the adapter resolves
to bytes only when it is about to send. Do not put bytes into `ImageReference`.

**Consequence 3, for the demo:** at 9.2 seconds per edit, a judge-edit-rejudge loop is roughly 15 to
20 seconds. Design the UI to be interesting while it runs, or pre-warm before presenting. Do not
leave dead air on stage.

### base64 output works, and it deletes the whole fetch problem

Probed 2026-08-06. Sending `response_format: "b64_json"` as a top-level field returns the image
**inline**, with no URL at all.

| Finding | Value |
|---|---|
| Request field | `response_format: "b64_json"`, top level. Accepted |
| Response | `data[0].b64_json` (162,808 chars, about 122 KB) and `data[0].mime_type` (`image/jpeg`) |
| `data[0].url` | **Absent.** Inline replaces it entirely |
| Cost | `200000000` = $0.020000. **Identical to the URL path.** No surcharge |
| Latency | 5,692 ms client, 5,489.0 ms server. Same as the URL path |

**Take this path. It removes an entire category of failure**, all of which we hit in sequence
tonight:

| Problem the URL path had | Status with base64 |
|---|---|
| Media served from `imgen.x.ai`, not `api.x.ai` | Gone. No second host |
| `HTTP 403` on the fetch, cause unknown | Gone. No fetch |
| Temporary URL expiry | Gone. Bytes arrive with the response |
| SSRF surface needing an allowlist, DNS checks, redirect refusal | Gone. No outbound request at all |
| Allowlist maintenance as xAI moves CDN hosts | Gone |

`fetch_provider_media` and its supporting machinery (`ALLOWED_MEDIA_HOSTS`,
`_assert_host_resolves_public`, the no-redirect handler) become **unreferenced**. Leave them in place
for now, clearly marked unused, and delete them in the Saturday cleanup if still unused. Do not do a
late-night refactor of security-critical code that currently passes its tests.

One exception was forced on 2026-08-06. `fetch_provider_media` carried
`assert parsed.hostname is not None`, and CI's `bandit -q -c pyproject.toml -r src` step fails on
**B101 assert_used** inside a security boundary, because `python -O` strips asserts. Replaced with an
explicit raise, which keeps the mypy narrowing and cannot be compiled away. The line was already
unreachable, since `_host_allowed` rejects every falsy hostname, so behaviour is unchanged and all
488 tests still pass. Four tests in `test_xai_live_contract.py` still import this machinery, so the
full deletion remains a Saturday job rather than a one-line cut.

### The bandit gate blocked a PR once already, and the evidence was nearly erased

**PR #9** was opened against `471bc14` at 2026-08-06T01:08:35Z, CI ran, and the **Scan for security
patterns** step failed. The PR was closed 76 seconds later at 01:09:51 and the branch was deleted
from origin. After that, `git ls-remote --heads origin canary/imagine-signal` returned nothing and no
PR was open, so the work looked like code that had simply never been pushed. The failure had already
happened and was invisible from every view you would normally check.

**The workflow run outlives the branch.** `gh run list --branch canary/imagine-signal` still finds
it. Look there before concluding that code is untested.

Diagnosed on 2026-08-06 by rebuilding a clean 3.13 venv exactly as CI does (`python3.13 -m venv` then
`pip install -e ".[test,serve,temporal]"`, never the repo's own `.venv`, which already carried `ruff`
and `bandit` from a different install path) and running every gate by hand:

| Gate | `main` cd218dd | canary 471bc14 | canary 53ad8d4 |
|---|---|---|---|
| `ruff check` / `ruff format --check` | pass | pass | pass |
| `bandit` | **pass** | **FAIL, exit 1** | pass |
| deterministic core, 100% line and branch | pass | pass, 100.00% | pass, 100.00% |
| `generate_imagine_signal_fixtures.py --verify-only` | pass | pass | pass |
| `run_imagine_signal_demo.py --verify-only` | pass | pass | pass |
| full suite, 55% floor | pass | pass, 85.63% | pass, 85.77% |
| `core-without-model-deps` | pass | pass | pass, 477 passed 3 skipped |

The local reconstruction landed on the same step CI had failed on, from evidence alone. ImagineSignal
introduced the repository's first bandit regression. **PR #10 on `53ad8d4` is green on both jobs**,
`lint-and-test` in 1m34s and `core-without-model-deps` in 24s.

Note the trigger list while you are here: `ci.yml` fires on `pull_request` and on `push` to `main`,
so **a branch push runs nothing at all.** Opening the PR is what runs CI. Run the gate set by hand
first, or the PR opens red, which is exactly how PR #9 went.

Payload size: about 122 KB per 1K image, so roughly 490 KB at `n=4`. Acceptable.

### Moderation: Grok Imagine WILL render the policy violation

Probed 2026-08-06 with the prompt "A product photo of a glass of beer on a wooden table, studio
lighting". **No moderation rejection.** Returned `data[0].b64_json`, 276,860 chars, `image/jpeg`,
`200000000` ticks, 5,757 ms.

This was the last blocking unknown for the repair-loop concept. The premise requires a creative that
violates an advertiser clause, and alcohol imagery is renderable, so a "no alcohol" clause is a
viable demo policy.

**Do not read this as "moderation is permissive."** It means one benign product shot of a legal
consumer good passed. It says nothing about other categories, and provider moderation rejection
remains terminal wherever it occurs.

**Payload size varies with image complexity:** 162,808 chars for the plain mug, 276,860 for the beer
shot, so roughly 122 KB to 208 KB per 1K image. Budget about 830 KB at `n=4`, not 490 KB.

### Implementation consequences for task 4

- **`extract_provider_response` needs a `headers` parameter.** Its current signature is
  `(raw, *, latency_ms)`, and the provider request id lives only in a header. Change the signature
  and the call site in `invoke` together.
- **The URL must be fetched immediately**, from an allowlisted xAI host, under strict size, type,
  redirect, and timeout controls, then hashed. Never persist only the URL.
- Media is **JPEG**. `assets.py` already accepts `image/(png|jpeg)` and parses JPEG dimensions by
  hand, so nothing changes there.
- Prefer `x-metrics-e2e-ms` over client-measured latency when it is present.

## 2. Price snapshot

Verified 2026-08-05 from `docs/imagine_signal/05_XAI_INTEGRATION.md`. Refresh
before quoting.

| Model | Image input | 1K output | 2K output |
|---|---:|---:|---:|
| `grok-imagine-image` | $0.002 | $0.02 | $0.02 |
| `grok-imagine-image-quality` | $0.01 | $0.05 | $0.07 |

One-reference edit totals: standard $0.022, quality 1K $0.06, quality 2K $0.08.

## 3. Spend log

Append one row per external call. Reported ticks only. If cost came back
unknown, write UNKNOWN and reconcile from the console before the next call,
because the client will block you until you do.

| # | Time | Model | Op | n | Reported ticks | USD | Qualified outputs | Note |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | 2026-08-05 17:37 | grok-imagine-image | generate | 1 | 200000000 | 0.020000 | n/a | Field-map probe 1 |
| 2 | 2026-08-05 17:37 | grok-imagine-image | generate | 1 | 200000000 | 0.020000 | n/a | Field-map probe 2, all headers |
| 3 | 2026-08-05 19:23 | grok-imagine-image | edit | 1 | 220000000 | 0.022000 | n/a | Edits endpoint probe, data URI reference |
| 4 | 2026-08-06 03:51 | grok-imagine-image-2026-03-02 | generate | 1 | 200000000 | 0.020000 | 0 | diagnose-generate: media host `imgen.x.ai` rejected by pre-fix allowlist |
| 5 | 2026-08-05 19:57 | grok-imagine-image-2026-03-02 | generate | 1 | 200000000 | 0.020000 | 0 | First spike run. Interlock logged UNKNOWN, but the provider DID report cost. RECONCILED |
| 6 | 2026-08-06 04:0x | grok-imagine-image-2026-03-02 | generate | 1 | 200000000 | 0.020000 | 0 | diagnose-generate after allowlist fix. HTTP 403 on media fetch |
| 7 | 2026-08-06 08:40 | grok-imagine-image | generate | 1 | 200000000 | 0.020000 | 1 | response_format=b64_json probe. WORKS, inline bytes |
| 8 | 2026-08-05 19:5x | policy-compiler (text) | compile | 1 | 367764000 | 0.036776 | n/a | Spike policy compile. Text is dearer than images |
| 9 | 2026-08-06 09:10 | grok-imagine-image | generate | 1 | 200000000 | 0.020000 | 1 | Beer prompt. NOT moderation-rejected. Concept C premise viable |
| 10 | | | | | | | | |

## 4. Running totals

| Metric | Value |
|---|---|
| Total calls | |
| Total reported ticks | |
| Total USD | |
| Qualified outputs | |
| **Cost per qualified output** | |
| Moderation rejections | |
| Unknown-cost events | |

The bolded row is the number worth saying out loud. It is the efficiency claim
the product is actually about, and it is measured rather than asserted.

## 5. Caps in force

| Cap | Value | Where enforced |
|---|---|---|
| Console postpaid limit | | `console.x.ai`, set Friday |
| `ExternalCallPolicy.max_total_cost_ticks` | | Constructor, rejects zero |
| `ExternalCallPolicy.max_calls` | | Per-client call counter |
| `ExternalCallPolicy.max_outputs_per_call` | | Checked before each invoke |
| Smoke probe ceiling | $0.25 | `hackathon/smoke_call.py` |

## 6. Honesty rules for these numbers

- Cost per qualified output is a real measured figure once this ledger is filled.
  It supports an efficiency statement about **this pipeline**.
- It does not support a claim about image quality, advertiser lift, causal lift,
  or X revenue. Those need evidence this project does not have.
- The synthetic 3-of-3 versus 2-of-3 comparison in the offline artifact is a
  fixture-backed pipeline check. It is not measured provider efficiency. Do not
  quote it as one.
