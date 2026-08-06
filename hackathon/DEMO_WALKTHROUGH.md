# Demo walkthrough: presenting what exists today

| Field | Value |
|---|---|
| Written | 2026-08-06 |
| Surface | `http://127.0.0.1:7860`, two tabs, Autopsy and ImagineSignal |
| Runtime | Fully offline. No API key, no network, no spend |
| Length | About 5 minutes at a walking pace, 3 if you cut section 4 |
| Audience | Daniel and Rohith first. The same path works for the xAI technical interview |

**This is not the Saturday demo script.** That one is in the concepts doc, section 8, and it describes a
product that does not exist yet. This document is for showing **what is actually built and running
right now**, which is a different and more defensible thing.

## Start it

```bash
cd /Users/arunsharma/code/adjacency && env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python app.py
```

Serves on `http://127.0.0.1:7860`. `Ctrl-C` stops it.

**Say the `env -u` prefix out loud when you demo.** It strips the API key out of the process, so the
running app physically cannot make a paid call. That is not a setting, it is the absence of a
credential, and it is the first honest thing on screen.

## The one-sentence frame, before you click anything

> "Two systems read the same advertiser policy. One is the keyword blocklist that ships today. One
> compiles the policy into something typed and hashed. I am going to show you every place they
> disagree, and then show you the system refusing to make a call it cannot back."

Do not open with architecture. Open with disagreement, because that is the part a reviewer can
evaluate without trusting you.

---

## Section 1: the Autopsy tab, before you run it

Land here. It is the interactive tab and it has motion.

**Point at the header.** `50 verified items · 18 local media`, sourced from
`corpus/frozen/manifest.json`. **The word "verified" is load-bearing:** the corpus is content-addressed
and checked, so the demo cannot quietly drift between runs.

**Point at the badge.** `DEMO MODE · FROZEN CORPUS · NO API KEY`.

> "Everything you are about to see replays from a frozen corpus. Same input, same output, every time.
> If I ran this on a plane it would behave identically."

---

## Section 2: press Run Autopsy. This is the moment

Press it. **The tables stream in rather than snapping**, because the runner yields frame by frame with
a 60 ms step. Let it play. Then **stop talking for two seconds** and let the red banner land.

```
GATE FAIL: G1_SPAN_NOT_FOUND
trace:x-2054959102195872231 changed from ALLOW to REVIEW and entered human review.
```

**That exact trace ID is the same every single time.** It is pinned in
`artifacts/ui/autopsy_snapshot.json` under `gate_fail_beat`, alongside `before_action: ALLOW` and
`after_action: REVIEW`. If you rehearse against this ID, it will be there on the day. If it ever is
not, the artifact changed and you should stop and find out why before demoing.

That banner is the entire thesis in one line, so give it room. Then:

> "The engine was going to allow that item. Gate G1 asked it to point at the exact span of text or
> region of the image that justified the verdict. It could not. So the decision was downgraded from
> ALLOW to REVIEW and handed to a person. Nothing about that is a model being cautious. It is a
> deterministic gate that fails closed."

**The three columns filled in at the same time. Walk them left to right.**

| Column | What it holds now | The line |
|---|---|---|
| **AGREE** | 14 traces, `ALLOW → ALLOW`, tiers T0 and T2 | "Most of the time the two systems agree. That is the honest baseline, and it is why the delta matters rather than the raw count" |
| **OVER_BLOCK** | 2 traces, `BLOCK → ALLOW`, T1, `Matched: deepfakes, synthetic media` | "The blocklist withheld these because the words 'synthetic media' appear. Read them: they are safe inventory. The advertiser paid nothing and reached nobody" |
| **UNDER_BLOCK** | 4 traces, `ALLOW → REVIEW`, T2, all `GATE FAIL · G1_SPAN_NOT_FOUND` | "And here it runs the other way. The blocklist would have served these. The engine could not cite evidence, so it stopped" |

**The T0 / T1 / T2 column is worth one sentence**, because it pre-empts the "isn't this just an
expensive LLM call" question:

> "T0 means it was decided deterministically with no model at all. T2 means it escalated. The cheap
> tier handles what it can, and the model only sees what actually needs judgment."

### The dollar counter, and how to say it

`$200.00 · Illustrative recovered-spend counter · 2 items × $100.00`, sourced from
`artifacts/ui/economics_assumption.json`.

**Say the word "illustrative" before anyone reads it.**

> "That two hundred dollars is two recovered items times a hundred-dollar placeholder I put in a config
> file. It is not measured revenue and the footer says so. I am showing you the counter because the
> shape is the product: over-blocks are countable. The number in it is a placeholder until an
> advertiser gives me a real one."

**Volunteering that is the strongest thing you do in the whole demo.** A reviewer who catches an
unlabeled dollar figure stops believing everything else on the screen.

**If somebody presses on it, you have a better answer than the footer.** Open the artifact:

```bash
cd /Users/arunsharma/code/adjacency && .venv/bin/python -c "import json;print(json.load(open('artifacts/ui/autopsy_snapshot.json'))['economics'])"
```

```
{'counter_value_usd': '200.00', 'evidence_class': 'illustrative_demo_input',
 'value_per_recovered_item_usd': '100.00'}
```

> "The label is not UI copy I could quietly delete. `illustrative_demo_input` is the evidence class
> carried in the artifact itself, next to the number. The data knows it is not a measurement."

That is a materially stronger claim than a disclaimer in a footer, and it is worth having ready.

---

## Section 3: click a row. The citation

Click any row in **Recovered inventory traces** (the OVER_BLOCK table).

The **Evidence inspector** fills in, with the **cited media region** beside it.

> "The verdict is not a score. It points at the specific region that drove it. A verdict that cannot
> cite its source does not pass G1, which is exactly what you watched fail thirty seconds ago."

Then open the **Audit drawer**: structured trace and the full gate chain.

> "That is every gate this item passed through, in order, with its result. Not a log. A record the
> receipt hashes."

---

## Section 4: the human review queue. Cut this first if short on time

Scroll to **Human review queue**: 9 rows.

Eight are `G1_SPAN_NOT_FOUND`. One is `G6_EFFORT_DISAGREEMENT`.

> "Everything the system refused to decide is here, with the reason. It does not silently drop
> anything and it does not guess. Note that one of these failed a different gate: G6 is effort
> disagreement, meaning two paths that should have converged did not. Different failure, same
> destination, a person."

**Point at the footer.** Four artifact paths, named. Then the sentence that ends the tab:

> "The dollar counter uses an illustrative input from `artifacts/ui/economics_assumption.json`, not
> measured revenue."

> "Every number on this screen has a file behind it, and the one number that does not is labeled."

---

## Section 5: the ImagineSignal tab. Same discipline, creative side

Switch tabs. **Lead with the sentence at the top of the panel**, because people assume this tab is
about generating images and it is not.

> "The product output is the decision receipt, not the images."

**Badge:** `DEMO MODE · FROZEN REPLAY · NO API KEY · READ ONLY`, and beside it
`run_mode fixture · network_used false · provider_call_used false`.

> "Read-only on purpose. There is no control on this screen that can trigger a generation or spend a
> cent."

**The three panels.** Control, `Variant · warm`, `Variant · cool`.

> "One approved image. Two variants. The only declared change is `background_tone`. Composition, logo,
> product identity and text are locked, and locked here means byte-verified, not promised: each panel
> carries its own `media_sha256`."

**Cost row: `0 ticks · status EXACT`.** Read the panel's own note out loud, because it is the sharpest
thing in the whole app:

> "Zero ticks here are the synthetic fixture's reported cost, not an absent measurement. An unreported
> provider cost would be unknown and would block further calls."

> "That distinction is the difference between a cost display and a cost control. Zero is a number the
> provider reported. If the provider reports nothing, the system records unknown and refuses to spend
> again until a human reconciles it."

**The gate ladder, `IS0` through `IS8`, all PASS.** Do not read all nine. Read the last one:

> "IS8 is the evidence-to-action ceiling. The evidence class here is FROZEN_REPLAY, and frozen replay
> permits a maximum action of TEST. Not publish, not spend, not rank. The receipt says production
> authorization: NOT_PRESENT."

**Finish on the section titled "Claims this surface will not make."**

> "I wrote the overclaims into the UI as a permanent list so that the demo argues against itself in
> public."

---

## Closing, 20 seconds

> "What is built: the policy compiler, the gates, the receipts, the cost interlock, a live xAI
> transport with nine real calls behind it, and both of these surfaces. 488 tests, CI green on a public
> branch with honest timestamps. What is not built is the repair loop, and that is deliberate, because
> it is the thing worth building on the day."

---

## Failure modes, and what to say

| If | Do | Say |
|---|---|---|
| Port 7860 is taken | `env -u XAI_API_KEY -u ADJ_RECORD .venv/bin/python app.py` after killing the old one, or set `GRADIO_SERVER_PORT` | nothing, just fix it |
| The page is blank on load | Hard refresh. Gradio occasionally loses the websocket | nothing |
| Someone asks for a live generation | **Do not run one.** The demo has no key loaded | "This build has no credential in the process. I have measured numbers from nine real calls and they are in the cost ledger" |
| Someone asks "is this real or mocked?" | Open the Audit drawer | "Frozen replay of real structure. The traces, gates and receipts are the production code paths. The corpus is frozen so the demo is deterministic" |
| Someone challenges the $200 | Agree immediately | "You are right to push on it. It is a placeholder and the footer labels it. The count of two is real, the hundred dollars is mine" |
| Wifi dies | Nothing. Keep going | "Worth noting this is still running. There is no network in this path" |

## What not to say

Straight from the claim rules, and they bind hardest when a demo is going well:

- No revenue, no lift, no improvement, no better images, no production ready.
- Not "it catches everything." It catches what it can cite, and routes the rest to a person.
- Not "the blocklist is bad." It is blunt in both directions, and both directions are on screen.
- **The `$200.00` is illustrative.** Say it before they ask, every time.
