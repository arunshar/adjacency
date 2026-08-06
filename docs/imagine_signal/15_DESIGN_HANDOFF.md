# Design handoff: the ImagineSignal presentation

| Field | Value |
|---|---|
| Version | 1.0 |
| Written | 2026-08-05 |
| Target | Extends the existing 9-slide Adjacency deck to 13 |
| Pipeline | `slides/_deck_data.json` then `build_deck.py`, `make_portable.py`, `render_all.sh`, `build_pptx.py`, `build_pdf.py` |
| Audience | Grokathon judges, then a 20-minute technical deep-dive |

This is the brief. The slide content itself is already wired into `slides/_deck_data.json`, so the
deck regenerates from the existing scripts with no new tooling.

## 1. The narrative arc

The existing deck argues one thing: **models propose, gates decide.** ImagineSignal does not start a
second argument. It shows the same discipline pointed at a second surface, which is a much stronger
position than "here is another feature".

| Act | Slides | Claim |
|---|---|---|
| Opening | 1 | Spatial Atlas discipline, pointed at ad adjacency |
| Problem | 2 | Blocklists are blunt in both directions |
| System | 3 to 4 | Compiled, not prompted. Every clause traces to authorizing words |
| Demo | 5 to 6 | The Autopsy: agree, over-block, under-block |
| Evidence | 7 | What is proven and what is not |
| Economics | 8 | The cost of being wrong in each direction |
| **Creative** | **9 to 12** | **Same discipline, second surface: controlled creative** |
| Close | 13 | One sentence someone repeats afterwards |

The join is slide 9. It must land as "the same idea, applied again", never as a pivot.

## 2. Slide-by-slide intent for the new block

### Slide 9, SYSTEM: "One image in. A family where exactly one thing changed."

**Must prove:** the discipline is the product, not the generation.

Fifty variants tell you nothing because you cannot attribute the difference. One axis at a time, with
locked attributes verified byte-identical, is what makes a comparison mean anything. Show the control
plus two variants and name the axis: `background_tone`.

**Visual:** three thumbnails, one labeled control, an explicit "only background_tone changed" caption.
Not a grid of many images. The restraint is the message.

### Slide 10, SYSTEM: "The provider is one method behind a typed port."

**Must prove:** this is a system, not a wrapper.

`ImagineTransport` is a Protocol with a single `invoke`. Replay is the default and needs no
credential. A missing fixture is terminal, with no fallback to a live call. An external call requires
an approved, cost-capped policy object.

**Visual:** [IS-03](diagrams/IS-03-transport-seam.svg), trimmed to the three modes and the cost
branch. Keep the "unknown cost blocks every later call" node visible. That detail is what a senior
engineer notices.

### Slide 11, EVIDENCE: "Nine gates, and a ceiling on what the evidence permits."

**Must prove:** the refusal to overclaim is mechanical.

`IS0` through `IS8`, fail-closed. The final action is the **most restrictive** of the proposal and
every failed gate's coercion. Frozen replay cannot authorize anything beyond `TEST`.

**Visual:** [IS-04](diagrams/IS-04-gate-chain.svg). If it is too tall for one slide, show the ceiling
half only: early evidence to `{HOLD, REVIEW, STOP}` versus later evidence to the full set.

### Slide 12, ECONOMICS: "Qualified evidence per generation dollar."

**Must prove:** the efficiency claim is measured, and correctly bounded.

Cost comes from the provider's reported ticks, per call, and an unreported cost is an explicit
unknown that halts spending rather than a zero.

**Fill this slide from `hackathon/COST_LEDGER.md` after the event.** If the ledger is empty at
presentation time, say the accounting is built and the figure is not yet measured. Do not estimate.

## 3. Visual system

Inherit the existing deck. Do not introduce a second language.

| Element | Rule |
|---|---|
| Layouts | Reuse `title`, `split`. Do not invent one |
| Kicker | Short, upper case, states the claim type |
| Title | One sentence, sentence case, `*emphasis*` marks the single key phrase |
| Body | 3 to 4 lines, each independently true |
| Highlights | 2 to 3 `{label, value}` pairs. The scannable layer |
| Notes | Full spoken paragraph. This is what `build_pptx.py` puts in presenter notes |
| Sources | Name the artifact path when a slide shows a number |
| Diagrams | The `IS-*` SVGs, one per slide, never two |

Colour keeps its meaning from the code: green admits, red blocks, amber is pending or unknown.

## 4. Claims that must not appear

An overclaim on a slide is worse than a missing slide, because it retroactively discounts everything
else.

| Never on a slide | Say instead |
|---|---|
| Better images, higher quality | One declared attribute changed, and we can prove which |
| Lift, uplift, improvement | The frozen replay reproduces exactly |
| Revenue, X revenue, monetization impact | Advertiser spend, only where the ledger has it |
| Production ready | Offline MVP, production NO_GO, ceiling TEST |
| Percentages with no artifact behind them | The artifact path, next to the number |

The synthetic 3-of-3 versus 2-of-3 comparison in the offline artifact is a **fixture-backed pipeline
check**. If it appears, the qualifier appears in the same breath, on the same slide.

## 5. Build

```bash
cd /Users/arunsharma/code/adjacency/slides && python build_deck.py && python make_portable.py
```

```bash
cd /Users/arunsharma/code/adjacency/slides && ./render_all.sh
```

```bash
cd /Users/arunsharma/code/adjacency/slides && python build_pptx.py && python build_pdf.py
```

Order matters. `build_pptx.py` requires `slides_png/slide_NN.png` for **every** slide in
`_deck_data.json` and raises `FileNotFoundError` if one is missing, so `render_all.sh` must run
first. `render_all.sh` defaults to slides 1 through 13 and drives headless Chrome.

`python-pptx` is not declared in `pyproject.toml`. It is present in the working `.venv`. See
[20_DRY_RUN_REPORT.md](20_DRY_RUN_REPORT.md) finding 4.

## 6. If you hand this to Claude Design

Give it this file, `diagrams/`, and `slides/_deck_data.json`. The useful brief is:

> Extend an existing 13-slide technical deck. Slides 9 through 12 are new and cover controlled
> creative mutation for ad imagery. Keep the existing visual language exactly. The argument is that
> the system refuses to claim more than its evidence supports, so restraint is the aesthetic: fewer
> images, more white space, one diagram per slide. Every number needs its artifact path beside it.
> Do not add any claim that is not already in the body text.

## 7. Rehearsal

- Three minutes, twice, out loud, timed. Slides 1, 5, 9, 11, 13 are the spine if you get cut short.
- One sentence per slide that you could say with the slide switched off.
- Know which slide you drop first if you lose two minutes. Recommended: slide 10, because slide 11
  carries the same argument with more force.
