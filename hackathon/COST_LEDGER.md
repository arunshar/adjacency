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
| Image location | `data[0].url` | **CONFIRMED.** A URL, not base64. 93 characters. Temporary |
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
| 3 | | | | | | | | |
| 4 | | | | | | | | |

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
