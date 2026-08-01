# Adjacency

**A brand-safety policy engine that compiles advertiser prose into something you can test.**

An advertiser writes their policy in three sentences of English. Adjacency compiles it into
a typed, hashed, diffable `PolicySpec`, evaluates inventory against it multimodally, passes
every verdict through seven deterministic fail-closed gates, and reports the delta against
what a keyword blocklist would have done, split into two directions that matter differently:

- **Under-blocks**: risk the blocklist could not see, because it was in the image.
- **Over-blocks**: safe inventory the blocklist demonetized.

The second one is the half that costs money and that nobody demos.

## The design claim

A language model does exactly three things here: compile prose into a `PolicySpec` (once,
cached), judge adjacency on the residual that survives deterministic triage, and write a
human-readable rationale. Everything else is a pure function.

**The rationale is display-only.** Every decision is computed from structured fields
(`action`, `severity`, `clause_ids`, `evidence`) that a gate checks mechanically. Prose is
never load-bearing. A model that writes a persuasive paragraph cannot argue its way past a
lookup table.

## The gates

| Gate | Checks | When |
|---|---|---|
| G0 | Every clause's span reproduces its quoted prose exactly | compile time |
| G1 | Every cited text span is present verbatim; every box lies inside its frame | per verdict |
| G2 | Every cited clause exists at that policy version | per verdict |
| G3 | A revision cannot flip a holdout item BLOCK to ALLOW without logged approval | per revision |
| G4 | `action` equals `SEVERITY_ACTION[severity]` | per verdict |
| G5 | Token, tool-call, and wallclock caps | per run |
| G6 | Below the confidence floor, or when two effort levels disagree, never ALLOW | per verdict |

G1 is the hallucination gate. G3 is the reward-hacking gate: absent it, the cheapest way to
make any brand-safety metric look good is to loosen the policy until everything is
deliverable, and the loosening is invisible because it shows up as more inventory rather
than as an incident.

Fail-closed means every failure resolves toward not serving an ad. `REVIEW` is a fail-closed
outcome, not a neutral one.

## Status

Early. The deterministic core (contracts and all seven gates) is implemented and tested.
The model layer, inventory fetcher, delta engine, and UI are next.

## Quick start

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/python -m pytest -q
```

The deterministic core has no model dependency. `pip install -e .` is enough to run every
gate test; `[model]` is only needed once you want to score real inventory.

## Layout

```
src/adjacency/
  contracts.py   the four frozen types: PolicySpec, InventoryItem, Verdict, DeltaRow
  gates.py       the seven gates, all pure functions
tests/
  test_gates.py  every failure branch of every gate
```

## Text offsets

Spans are character offsets into NFC-normalized text, not bytes and not UTF-16 code units.
This is load-bearing on a platform whose posts are full of emoji. The family emoji is 1
grapheme, 7 Python characters, 25 UTF-8 bytes, and 11 UTF-16 code units, and a model asked
for "the byte offset" will not reliably give you any of those. `Evidence.quote` is the
source of truth; the offsets are a claim about where it appears, and G1 checks that claim
rather than trusting the model's arithmetic.

## License

MIT.
