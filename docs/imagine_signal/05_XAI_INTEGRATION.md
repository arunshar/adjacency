# xAI and X integration note

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Verified against official documentation, plus unresolved account-specific checks |
| Author | Arun Sharma |
| Verified | 2026-08-05 |
| Source policy | Official xAI and X documentation only |

## 1. Direct answer about SuperGrok

Your SuperGrok subscription helps with manual prompt exploration, image trials in Grok, and rapid comparison while designing the controlled mutation family.

Do not assume it removes the developer setup or pays for production API calls. Official xAI account and billing documentation says API keys are team-bound and API consumption is billed through the xAI Console using prepaid credits or approved invoicing. A newer consumer FAQ shows an `API` category in SuperGrok's shared weekly usage view, but it does not define whether that means public developer API calls or how it interacts with team billing.

Safe implementation rule:

1. Use SuperGrok for manual creative exploration.
2. Sign in to `console.x.ai` with the same account.
3. Confirm the selected team's API credit balance and enabled image models.
4. Create a scoped API key.
5. Set a zero postpaid limit or another explicitly approved cap.
6. Run the project offline until one bounded smoke call is approved.

Treat any subscription-included developer allowance as unverified until the Console shows it for this account.

## 2. Verified Imagine API surface

REST base URL:

```text
https://api.x.ai/v1
```

Image endpoints:

```text
POST /images/generations
POST /images/edits
GET  /image-generation-models
GET  /image-generation-models/{model_id}
```

Authentication:

```text
Authorization: Bearer $XAI_API_KEY
Content-Type: application/json
```

The first-party `xai-sdk` supports synchronous and asynchronous image clients. OpenAI-compatible clients support image generation, but xAI documents that OpenAI SDK `images.edit()` is not compatible with xAI's JSON image-edit endpoint. Use the xAI SDK or direct JSON HTTP for edits.

## 3. Models and price snapshot

Prices below were verified on 2026-08-05 and must be refreshed before budgeting or review.

| Model | Use | Image input | 1K output | 2K output | Documented rate limit |
|---|---|---:|---:|---:|---:|
| `grok-imagine-image` | Standard exploration | $0.002 per input image | $0.02 per output | $0.02 per output | 5 requests per second |
| `grok-imagine-image-quality` | Finalist quality or higher-fidelity edits | $0.01 per input image | $0.05 per output | $0.07 per output | 5 requests per second |

One-reference edit examples at this snapshot:

- Standard 1K or 2K: $0.002 input plus $0.02 output, totaling $0.022.
- Quality 1K: $0.01 input plus $0.05 output, totaling $0.06.
- Quality 2K: $0.01 input plus $0.07 output, totaling $0.08.

The API response includes `usage.cost_in_usd_ticks`, where 10,000,000,000 ticks equal one US dollar. Store this actual request cost. Do not rely only on the price table.

Documented aliases include:

- `grok-imagine-image-2026-03-02`
- `grok-imagine-image-quality-20260403`
- `grok-imagine-image-quality-latest`

Use a dated alias for reproducible evaluation. Use a moving stable alias only when automatic model upgrades are desired and the claim-expiration policy is active.

## 4. Relevant capabilities

- Text-to-image generation.
- Single-image editing through public URL, base64 data URI, or Files API `file_id`.
- Multi-image editing with up to three reference images.
- Multiple outputs per request.
- 1K and 2K resolution.
- A range of aspect ratios, including 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 2:1, 1:2, and auto.
- URL or base64 output.
- Response metadata for resolved model and moderation behavior in the xAI SDK.
- Bounded concurrent requests for different prompts.
- Same-prompt batch generation through `n`.
- Batch API support for offline image work, billed at normal image rates.
- Files API reuse and persistence.

## 5. Mapping to controlled creative mutation

### Text-to-image family

Use when there is no approved base image. Compile a stable prompt prefix containing product, brand, composition, offer, and locked constraints. Append exactly one controlled mutation level.

### Image-edit family

Use when an approved base exists. Send the same base image for every child and vary one edit instruction. This is the preferred conceptual path because the parent is explicit, but the output must still be checked for unintended drift.

### Same prompt with `n`

Use `n` when several samples represent the same mutation level. Do not label random same-prompt samples as different controlled levels unless each level has its own declared request.

### Different controlled prompts

Use separate requests with bounded concurrency. Each request retains its own mutation ID and request hash.

### Multi-image editing

Use only when the references have declared roles, such as product, setting, and brand style. Multi-image editing increases the chance that more than one visual factor changes, so it is P1 rather than the first demo path.

## 6. Efficient generation policy

The efficiency objective is qualified evidence per generation dollar, not raw images per second.

1. Validate the brief and locked constraints before any paid call.
2. Check whether the canonical request already has a replay fixture or prior output.
3. Use the standard model for broad low-cost exploration.
4. Reject corrupt, moderation-failed, or duplicate outputs before more calls.
5. Admit only promising, controlled candidates to the quality model.
6. Reuse a private `file_id` for iterative edits when retention policy permits it.
7. Use same-prompt batching only within one mutation level.
8. Use bounded concurrency for distinct levels and respect 5 requests per second.
9. Log actual response cost and enforce family and daily dollar caps.
10. Stop a family when evidence says another generation is not justified.

The Batch API avoids real-time rate limits for large offline jobs, but current documentation says image batches receive no price discount and may take up to roughly 24 hours on a best-effort basis.

## 7. Output persistence

Default generation URLs are temporary. Production code must not save only the URL.

Prototype options:

- Request base64 output, decode immediately, validate, hash, and store the bytes. Do not write raw base64 into logs or JSON fixtures.
- Accept the temporary URL only from an allowlisted xAI host, fetch immediately with strict size, type, redirect, and timeout controls, then hash the bytes.

Production option:

- Use `storage_options` to persist an output to the xAI Files API and retain its private `file_id`, subject to data-retention, regional, deletion, and storage-cost review.

File storage and downloads are separately billed. Refresh the official price before choosing this as the primary asset store.

## 8. Moderation and provenance

- Record the provider's moderation disposition when exposed.
- A moderation failure is terminal for that output. Do not retry alternative wording to evade the result.
- Existing X Ads policy, advertiser-integrity, brand, legal, and human approvals remain separate gates.
- Do not promise watermark-free or ad-ready outputs until an actual API response and the applicable brand and provenance rules are reviewed.
- xAI policy prohibits removal of embedded provenance or watermarks.

## 9. Replay and live recording

The repository's current `FixtureStore` is replay-first and secret scans JSON requests. ImagineSignal should extend the pattern for binary assets.

### Default fixture mode

- No `XAI_API_KEY` required.
- No network client constructed.
- Missing fixtures produce a visible error.
- No automatic live fallback.

### Explicit record mode

- Requires `ADJ_RECORD=1` and `XAI_API_KEY`.
- Requires a predeclared call, image, model-tier, and dollar cap.
- Uses non-sensitive prompts and assets only for committed fixtures.
- Downloads or decodes the output immediately.
- Records sanitized provider metadata, actual cost, and media digest.
- Removes the credential and reruns replay before accepting the fixture.

Do not reuse a consumer-app image manually as proof that the API contract works. The app and API are separate execution surfaces.

## 10. Account preflight for August 6

These are user-owned checks in the browser or Console. Do not paste an API key into a review document, issue, fixture, chat, or shell history.

1. Open the SuperGrok Usage page and note whether an API category appears.
2. Open `console.x.ai` and select the intended personal team.
3. Check API credit balance, postpaid limit, and auto top-up state.
4. Check that `grok-imagine-image` and `grok-imagine-image-quality` are enabled.
5. Create a least-privilege key for local development.
6. Keep postpaid usage disabled or set an approved low cap for the smoke test.
7. Confirm the model-discovery endpoint with the key.
8. Make at most one approved standard 1K non-sensitive generation call.
9. Record the actual `cost_in_usd_ticks`, model, moderation field, request ID, and output behavior.
10. Revoke or rotate the development key after recording if it was exposed to any unsafe surface.

If the Console shows no credit or model access, continue entirely in fixture mode. That does not block the first implementation slice.

## 11. X Ads integration reality

X Ads API access is separate from xAI API access. It requires an approved X developer application, Ads API access for that application, OAuth 1.0a user context, and authorization for the relevant advertiser account.

Documented analytics can include creative-level impressions, clicks, engagements, and billed advertiser spend. Attributed purchase value exists only when the advertiser has configured and supplied conversion values. The public Ads API does not expose X's internal publisher revenue, auction profit, or the complete counterfactual auction state required for a revenue replay.

For a future external prototype:

- Map each controlled creative ID to an unambiguous promoted-post or creative entity ID.
- Call monetary fields `advertiser spend` or `attributed purchase value`, as appropriate.
- Do not label either as platform revenue.
- Treat analytics as mutable during the documented adjustment window.
- Use the Ads sandbox only to prove workflow wiring. Sandbox campaigns do not serve and cannot establish response or revenue lift.

The current MVP has no X Ads API dependency.

## 12. Verified sources

- [xAI Imagine overview](https://docs.x.ai/developers/model-capabilities/imagine)
- [Image generation](https://docs.x.ai/developers/model-capabilities/images/generation)
- [Image editing](https://docs.x.ai/developers/model-capabilities/images/editing)
- [Multi-image editing](https://docs.x.ai/developers/model-capabilities/images/multi-image-editing)
- [Imagine Files API integration](https://docs.x.ai/developers/model-capabilities/imagine/files)
- [Standard image model](https://docs.x.ai/developers/models/grok-imagine-image)
- [Quality image model](https://docs.x.ai/developers/models/grok-imagine-image-quality)
- [xAI pricing](https://docs.x.ai/developers/pricing)
- [xAI cost tracking](https://docs.x.ai/developers/cost-tracking)
- [xAI API quickstart](https://docs.x.ai/developers/quickstart)
- [xAI API account FAQ](https://docs.x.ai/console/faq/accounts)
- [xAI API billing](https://docs.x.ai/console/billing)
- [Grok consumer FAQ](https://docs.x.ai/grok/faq)
- [X Ads API access guide](https://docs.x.com/x-ads-api/getting-started/step-by-step-guide)
- [X Ads analytics](https://docs.x.com/x-ads-api/analytics)
- [X Ads sandbox](https://docs.x.com/x-ads-api/fundamentals/sandbox)

## 13. Unresolved items

1. The exact developer-API entitlement, if any, included in this SuperGrok account's shared weekly pool.
2. The actual team credit balance, enabled models, and permissions.
3. The exact lifetime of a normal real-time generation URL.
4. Watermark behavior for the selected API model and account.
5. Whether internal hackathon access includes a pre-approved X Ads application or advertiser account.
6. Quantitative latency and quality differences between standard and quality models, which must be benchmarked rather than assumed.
