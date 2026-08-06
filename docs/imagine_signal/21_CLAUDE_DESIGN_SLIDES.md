# Claude Design import: the overall project deck

| Field | Value |
|---|---|
| Written | 2026-08-06 |
| Purpose | Regenerate the full Adjacency + ImagineSignal deck in Claude Design |
| Relationship to `slides/` | **Parallel artifact, not a replacement.** `slides/_deck_data.json` stays the build source of record for the PPTX and PDF |
| Companion | `15_DESIGN_HANDOFF.md` covers slides 9 to 12 only. This covers all 13 |
| Length | 13 slides, about 12 minutes spoken, 3 minutes if you run the DEMO block alone |

**Paste section 6 into Claude Design.** Sections 1 through 5 are the source material it needs; section
7 is your own check and does not go in.

**Why regenerate at all when `slides/` already builds a deck?** The existing pipeline is strict:
`build_deck.py` then `make_portable.py` then `render_all.sh` then `build_pptx.py` then `build_pdf.py`,
and `build_pptx.py` raises `FileNotFoundError` unless a PNG exists for every slide. That is the right
pipeline for a frozen release artifact and the wrong one for iterating on wording the night before a
talk. Use Design to explore, then fold anything you keep back into `_deck_data.json`.

---

## 1. The design system, copied from the built deck

Give Design these values verbatim so the generated deck sits beside the existing PPTX without a
visible seam.

| Token | Value | Use |
|---|---|---|
| `bg` | `#08111F` | Slide background |
| `bgAlt` | `#101C2F` | Panels, table fills, code blocks |
| `ink` | `#F4F7FB` | Primary text |
| `inkDim` | `#A8B4C8` | Subtitles, footers, secondary labels |
| `accent` | `#22D3EE` | Cyan. The emphasized words in a title, and the title rule |
| `accent2` | `#F97316` | Orange. The baseline or incumbent method, only |
| `good` | `#4ADE80` | PASS states |
| `warn` | `#FBBF24` | Coercion, REVIEW, held states |
| `grid` | `#2A3A53` | Chart gridlines, table borders |
| `pcrf` | `#38BDF8` | **Light blue. Model output and proposal boxes** in every diagram |
| `pigrpo` | `#F43F5E` | **Rose. Gate boxes, and the Tier 2 bar.** This is the colour a gate is |

**Those last two names are residue and their colours are not.** `build_deck.py` was forked from
`~/Desktop/pcrf-monorepo/slides/build_deck.py`, and the two tokens kept that project's names. They are
live: `pcrf` renders the "Structured call" and "Proposed ALLOW" boxes, and `pigrpo` renders "G0
admission", the Tier 2 bar, and the `G1_SPAN_NOT_FOUND` box on slide 6. **Omitting them would recolour
the centre slide of the deck.** Keep the values, and if you rename them, rename in `_deck_data.json`
and in the five references inside `build_deck.py` together.

The semantic pairing is worth stating to Design explicitly, because it is the deck's visual argument
in miniature: **what the model proposed is light blue, what the gate did is rose.** Every diagram
repeats that pairing, so by slide 6 the audience already reads rose as "the system stopped."

**Fonts:** `Space Grotesk` for headings, `Inter` for body, `JetBrains Mono` for every identifier,
metric, and file path.

**Slide furniture, consistent on all 13:**

- A section kicker at top left in mono caps: `OPENING`, `PROBLEM`, `SYSTEM`, `DEMO`, `EVIDENCE`,
  `ECONOMICS`, `CREATIVE`, `CLOSE`.
- Title at about 40px, max 27 characters per line, with **one or two emphasized words in `accent`**.
- A 64px by 2px rule in `accent` under the title.
- Footer: section name at left, `NN / 13` at right, both in `inkDim`.

**The emphasis rule is the whole visual identity.** Exactly one idea per title is highlighted in cyan.
If two things are emphasized, the slide has two arguments and should be two slides.

---

## 2. Verified state as of 2026-08-06

Every number Design is allowed to put on a slide, with where it came from. **Nothing outside this
table may appear as a figure.**

| Fact | Value | Source |
|---|---|---|
| Test suite | `488 passed`, no xfails | local run and CI |
| Deterministic core coverage | 100 percent line and branch | CI gate |
| Package coverage | 85.77 percent | CI floor is 55 |
| CI | Green on both jobs, draft PR #10 | `canary/imagine-signal` |
| Live provider calls | **9 calls, $0.199 total** | `hackathon/COST_LEDGER.md` |
| Standard 1K generation | $0.02, 5.3 to 5.5 s | `x-metrics-e2e-ms` header |
| Edit through `/images/edits` | $0.022, 9.2 s, about 1.75x a generation | measured |
| Policy compilation | **$0.0368, dearer than an image** | measured |
| Payload per 1K image | 122 to 208 KB inline base64 | measured |
| Rate budget | 300 requests | provider header |
| Frozen corpus | 50 verified items, 18 local media | `corpus/frozen/manifest.json` |
| Human review queue | 9 items | `artifacts/ui/autopsy_snapshot.json` |
| Offline artifact digest | `b17e9105...f621ca73` | `artifacts/imagine_signal/offline_demo.json` |

**The one dollar figure that is not measured:** the `$200.00` recovered-spend counter in the Autopsy
demo. It is 2 items times a $100 placeholder, and the artifact itself carries
`evidence_class: illustrative_demo_input`. **If it appears on a slide it must be labeled illustrative
in the same visual block, not in a footnote.**

---

## 3. The narrative arc

Eight sections, thirteen slides. The arc is: *here is a real problem, here is a system, watch it
work, watch it refuse, here is what it costs, here is what we will not claim.*

| Slides | Section | Job |
|---|---|---|
| 1 | OPENING | Establish the discipline being pointed at a new domain |
| 2 | PROBLEM | Why the incumbent method fails in both directions |
| 3, 4 | SYSTEM | The pipeline, and the provenance rule that makes it auditable |
| 5, 6 | DEMO | The delta, then the refusal. **Slide 6 is the emotional centre of the deck** |
| 7, 8 | EVIDENCE | The failure path is the strongest evidence. The cost ladder is bimodal |
| 9 to 12 | CREATIVE | ImagineSignal: controlled mutation, the provider seam, nine gates, the economics |
| 13 | CLOSE | What is real, what is offline, what is staged |

**Slide 6 carries the deck.** A persuasive rationale cannot argue past `G1_SPAN_NOT_FOUND`. Everything
before it earns the right to make that claim and everything after it inherits the credibility. If a
slide has to be cut for time, never cut 6.

---

## 4. Slide-by-slide

Titles below are the existing ones. `*asterisks*` mark the words to emphasize in `accent`.

### 1. OPENING: Spatial Atlas discipline, pointed at *ad adjacency*

Frame the transfer: the same verification discipline used for spatial data, aimed at brand safety.
**Do not open with architecture.** Open with the claim that models propose and gates decide.

### 2. PROBLEM: Keywords are legible, but the risk is often *between modalities*

The incumbent is a keyword and handle blocklist. Show that it is blunt in **both** directions: it
withholds safe inventory and it serves risky inventory. Use `accent2` orange for the blocklist
throughout the deck so the eye learns which side is which.

### 3. SYSTEM: Compile intent, inspect inventory, admit evidence, compare outcomes, receipt

The five-stage pipeline. One horizontal flow, no boxes-and-arrows sprawl. Gates `G0` through `G6`
labeled on the stages where they fire.

### 4. SYSTEM: Every clause must point back to the *words that authorized it*

Provenance. A clause that cannot cite its source never compiles. **This slide sets up slide 6**, so
the phrase "cite its source" must appear here in the same words used there.

### 5. DEMO: Both directions matter: missed risk and *recovered safe inventory*

The delta, split into over-blocks and under-blocks. Real counts from the frozen corpus. If the
`$200.00` counter appears, the word **illustrative** appears in the same block.

### 6. DEMO: A persuasive rationale cannot argue past *`G1_SPAN_NOT_FOUND`*

The refusal. Show the real beat from the demo:

```
trace:x-2054959102195872231    ALLOW -> REVIEW    G1_SPAN_NOT_FOUND
```

Then the human review queue, 9 items. **The design job here is restraint.** One trace, one transition,
one gate code, large. No table, no chart. The audience needs three seconds of silence to read it.

### 7. EVIDENCE: The strongest numbers test the *failure path*

Coverage and the fault-injection harness. The argument: passing tests prove a system works, and
injected faults prove it fails correctly, which is the harder and more interesting property.

### 8. ECONOMICS: The measured ladder is *bimodal*, not a smooth curve

Tier 0 costs nothing and decides a real share of inventory. Escalated tiers cost the model call. The
distribution has two modes, not a gradient. **This is where the $0.0368 policy-compilation figure
belongs**, because it is the counterintuitive one: text is dearer than an image.

### 9. CREATIVE: One image in. A family where *exactly one thing* changed.

The control plus two variants, `background_tone` moved, everything else byte-locked with
`media_sha256` shown. Use the real fixture images from the running demo, not mockups.

### 10. CREATIVE: The provider is *one method* behind a typed port.

`ImagineTransport.invoke` as a Protocol, replay-first, no credential lookup in the library.

**Update from the built deck:** the live path now uses `response_format: "b64_json"`, which deleted
the entire URL-fetch and SSRF surface. No second host, no allowlist to maintain, no expiring link.
That is a slide-worthy simplification and it was found by probing rather than by design.

### 11. EVIDENCE: Nine gates, and a ceiling on *what the evidence permits*.

`IS0` through `IS8`. Land on IS8: the evidence-to-action ceiling. `FROZEN_REPLAY` permits a maximum
action of `TEST`. Production is `NO_GO`. Show the ordering as a ladder, not a list.

### 12. ECONOMICS: The objective is *qualified evidence per generation dollar*.

Cost per **qualified** output, where qualified means it passed every gate. The 9 calls and $0.199 go
here, as the honest denominator behind the framing.

### 13. CLOSE: Real Cloud review, offline demo, staged rollout

What is real: 488 tests, CI green, a public branch with honest timestamps, nine real provider calls.
What is offline: the whole demo, verified with the network off. What is staged: everything else.

**End on the refusal, not on a roadmap.** The last line the room should hear is that the system will
not recommend an action its evidence does not support, and that this is enforced in code.

---

## 5. Claims that must not appear

Binding on anything Design generates, including connective copy it writes itself.

**Never:** revenue or revenue impact of any kind, lift, uplift, improvement, better images, higher
quality, production ready, causal claims about advertiser outcomes, "days to seconds" or any
unmeasured cycle-time comparison, or any suggestion that the system works around provider moderation.

**Instead:** advertiser value, cost per qualified output, the frozen replay reproduces exactly, one
declared attribute changed and we can prove which, offline MVP with an action ceiling of `TEST`.

**Two specific traps:**

1. The synthetic 3-of-3 versus 2-of-3 comparison in the offline artifact is a fixture-backed pipeline
   check. It is the most quotable and most misquotable number in the project. If it appears, the
   qualifier appears with it.
2. `0 ticks · status EXACT` in the ImagineSignal panel is the fixture's **reported** cost, not a
   missing measurement. Never render it as "free."

**Plain ASCII hyphens only. No em dashes and no en dashes anywhere.**

---

## 6. The paste-in brief for Claude Design

> Build a 13-slide presentation deck as a single self-contained dark HTML file with keyboard
> navigation and a speaker-notes pane.
>
> Palette: background `#08111F`, panels `#101C2F`, text `#F4F7FB`, dim text `#A8B4C8`, accent cyan
> `#22D3EE`, secondary orange `#F97316`, good `#4ADE80`, warn `#FBBF24`, gridlines `#2A3A53`. Fonts:
> Space Grotesk for headings, Inter for body, JetBrains Mono for every identifier, metric and file
> path. Inline everything; no external font or asset requests.
>
> Diagrams use a fixed two-colour semantic pairing that must hold on every slide: **what the model
> proposed is light blue `#38BDF8`, what a gate did is rose `#F43F5E`.** Orange `#F97316` is reserved
> for the incumbent keyword blocklist and appears nowhere else.
>
> Every slide carries a mono uppercase section kicker at top left, a title around 40px with exactly
> one or two words emphasized in cyan, a 64x2px cyan rule under the title, and a footer with the
> section name at left and `NN / 13` at right.
>
> Sections in order: OPENING, PROBLEM, SYSTEM (2 slides), DEMO (2), EVIDENCE, ECONOMICS, CREATIVE (4),
> CLOSE. The subject is Adjacency, a brand-safety policy engine that compiles an advertiser's prose
> policy into a typed hashed spec, evaluates inventory through deterministic fail-closed gates, and
> emits an append-once decision receipt, plus ImagineSignal, which applies the same discipline to
> controlled creative variation.
>
> Slide 6 is the centre of the deck and must be the most restrained: a single trace changing from
> ALLOW to REVIEW under gate code `G1_SPAN_NOT_FOUND`, large, with no table and no chart.
>
> Only these figures may appear: 488 tests passing, 100 percent line and branch on the deterministic
> core, 9 live provider calls totalling $0.199, $0.02 and 5.3 to 5.5 seconds per standard 1K image,
> $0.022 and 9.2 seconds per edit, $0.0368 to compile a policy, a 300-request budget, a frozen corpus
> of 50 verified items, and a 9-item human review queue. Do not invent or extrapolate any other
> number.
>
> Do not state or imply revenue, lift, improvement, better image quality, production readiness, or any
> causal advertiser outcome. Use plain ASCII hyphens only, never em or en dashes.

---

## 7. Your check before you present from it. Do not paste this section

- [ ] Every figure on every slide appears in the table in section 2. Anything else is invented.
- [ ] The `$200.00` counter, if used, says **illustrative** in the same block.
- [ ] Slide 6 has exactly one trace on it. If Design added a table, delete the table.
- [ ] Slide 10 says inline base64, not URL fetch. The built PPTX predates that change.
- [ ] The deck ends on the refusal, not on a roadmap slide Design added for symmetry.
- [ ] No em dashes. Design inserts them by default and the check is a grep, not a read.
- [ ] If you keep any wording, fold it back into `slides/_deck_data.json` so the PPTX and this deck do
      not drift. Build order is strict: `build_deck.py`, `make_portable.py`, `render_all.sh`,
      `build_pptx.py`, `build_pdf.py`.
