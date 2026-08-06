# Contingency plan: the brief is unknown until Saturday morning

| Field | Value |
|---|---|
| Version | 1.0 |
| Written | 2026-08-05, after Victoria Mackey's reply |
| What changed | The build is **assigned on the day**. No interview slots. No provider details. |
| Governing rule | **The asset is the harness, not ImagineSignal.** |

## 1. What the organizer actually said

Three facts, and each one invalidates something in the earlier plan.

| Statement | Consequence |
|---|---|
| "Details on what you'll be building will be shared the morning of the event" | This is a **prescribed brief**, not a free-form hackathon. ImagineSignal is probably **not** the submission. |
| "No remaining open slots available for interviews during the event" | The 20-minute technical deep-dive is not happening on Saturday. Recruiters will be onsite for informal conversation. |
| Nothing about API access or credentials | Provider availability is **unknown**. Plan for every tier including no model at all. |

Nothing here is bad news. It removes a theme-guessing risk and replaces it with a preparation
problem, which is the kind you can actually solve in advance.

## 2. The reframe

Stop thinking of Saturday as "present ImagineSignal." Think of it as: **at 09:00 you receive a brief,
and you are the only person in the room holding a tested substrate for turning a model's output into
a defensible decision.**

What is genuinely reusable, none of it advertising-specific:

| Asset | What it gives you on an unknown brief |
|---|---|
| `gates.py` (`G0`-`G6`) + `imagine_signal/gates.py` (`IS0`-`IS8`) | Fail-closed admission with coercion and a total restrictiveness ordering |
| `decisions.py` | Evidence classes and an action ceiling. Stops the demo from overclaiming |
| `canonical.py` + `receipts.py` | Deterministic hashing and append-once, tamper-evident receipts |
| `ports.py` / `xai.py` `ResponseClient` | Two replay-first provider seams, both Protocol-based |
| `sources.py` (`ADJ_SOURCE`) | Four data tiers already abstracted behind one env var |
| `tier_zero.py` | Decisions with **no model at all** |
| `synthetic_faults.py` | Fault-injection eval harness |
| 448 tests, CI, deterministic artifacts | Credibility you cannot build between 09:00 and 21:00 |

`docs/RETARGETING.md` already names exactly what is domain-shaped and what is not, and it was
written before this constraint existed. It is the most valuable document in the repository today.

## 3. Provider contingency ladder

Assume nothing about what they hand out. Every tier below is demoable.

| Tier | Condition | What you run | Prep needed |
|---:|---|---|---|
| **T0** | No model, no key, no network | `tier_zero.decide_tier_zero` plus the deterministic gates. The Autopsy demo runs offline. | **None. Verified working with wifi off.** |
| **T1** | No live access, fixtures only | Frozen replay through `FixtureImagineClient` / `RecordedXAIClient` | None. This is the default path |
| **T2** | They provide a key or endpoint | Inject it at the existing seam. `ResponseClient` for text, `ImagineTransport` for images | ~30 min: one adapter class |
| **T3** | Your own console key with credit | Same seam, your `ExternalCallPolicy` cap | Friday preflight |
| **T4** | Emergency, non-xAI | `litellm` is already in the `model` extra | Last resort. At an xAI event this is a bad look. Use only to keep a demo alive |

**The design property that makes this cheap:** both provider seams are Protocols with replay as the
default and no credential lookup inside the library. Swapping providers is writing one class, not
refactoring the app. That was verified end to end with zero network during the dry run.

## 4. The 09:00 decision, and when NOT to reuse the foundation

Read the brief, then answer one question honestly:

> **Does the brief involve a model or agent producing an output that somebody has to trust?**

| Answer | Move |
|---|---|
| **Yes** (evaluation, moderation, agents, safety, ranking, extraction, classification, grading, verification, anything with a judge) | Retarget the harness. Section 5. This is the strong case and it is a large share of realistic briefs |
| **Partly** (a product where trust is one component) | Build the product normally, drop in gates and receipts for the one component that needs defending. Cheap, high signal |
| **No** (build a game, a visualization, a Slack integration, a pure UI) | **Start fresh. Do not force it.** |

**The trap to avoid.** Bolting a verification harness onto a brief that does not need one reads as
"he had a hammer." That is worse than a clean small build. If the brief does not need it, say so, use
the general engineering strength instead, and keep the foundation as a portfolio conversation with
the recruiters rather than as the submission.

**The honest limit**, already documented in `docs/RETARGETING.md`: evidence is text spans or image
boxes, and decisions are three-way. A brief whose evidence is audio timestamps or video frame ranges
needs a new `Evidence` variant and a matching G1 branch. That is real work, not a rename.

## 5. The 90-minute retarget

If the answer is yes. All of this is mechanical and the test suite catches misses.

| Minutes | Step |
|---:|---|
| 0-10 | Write the brief down in one sentence. Name the thing being judged and what a wrong judgement costs |
| 10-25 | Rename per `docs/RETARGETING.md` section 3: `advertiser` to `owner`, `InventoryItem` to `ContentItem`. Run the suite |
| 25-45 | Rewrite the severity table in `contracts.py` for the new domain's consequences |
| 45-70 | Replace the baseline. `BaselineMatcher` compares against a keyword blocklist because that is the ads product. Substitute whatever the incumbent method is in the new domain, **generated from the same source policy** so the comparison stays honest |
| 70-90 | Repoint the corpus with `ADJ_SOURCE`. Build 5 to 10 fixtures for the new domain |

After 90 minutes you have a domain-correct, gated, receipted system with a passing suite while other
teams are still choosing a framework.

**Keep `IS0`-`IS8` and ImagineSignal out of it** unless the brief is about creative generation. Do
not drag in a second domain to justify prior work.

## 6. What to say to the recruiters

There is no scheduled interview, so this is a corridor conversation. Different artifact, different
length.

**The 40-second version, if asked what you work on:**

> "My research is on knowing when a model's output is trustworthy enough to act on, in settings where
> acting wrongly is expensive. I built a system that takes an advertiser's brand-safety policy in
> plain prose, compiles it into a typed hashed spec, and passes every verdict through deterministic
> fail-closed gates before anything ships. The point is that it refuses to claim more than its
> evidence supports, and the refusal is enforced in code rather than in a style guide."

Then stop. Let them ask.

**Have ready, but do not lead with:**

- The repository link, once the canary branch is public.
- One sentence on the coverage asymmetry: decision core at 100 percent line and branch, I/O against a
  55 percent floor, because a bad verdict from a bad I/O layer still gets caught by the gates.
- The honest limit, unprompted: it is offline, the auction piece is simulated, and there is no causal
  evidence. Volunteering that is a strength signal.

**Do not:** hand over a laptop uninvited, quote a number you have not measured, or claim a hackathon
placement. There is no verified hackathon win on your record and you do not need one.

`~/code/adjacency-prep/imagine-signal-interview-prep.html` is not wasted. It is now prep for a
**later scheduled** interview, not for Saturday. Page 4 (real vs simulated) and page 11 (glance card)
still apply verbatim to a corridor conversation.

## 7. Saturday timeline, revised

| Time | Revised |
|---|---|
| Before 09:00 | Environment built, offline demo verified with wifi off, canary branch pushed and tagged. **Do this Friday** |
| 09:00 | Read the brief. Answer the section 4 question. Write the one-sentence restatement |
| 09:15 | Commit the decision. Reuse or fresh. **Do not revisit it at noon** |
| 09:30-11:00 | If reusing: the section 5 retarget. If fresh: scaffold with the same discipline, gates and receipts from the start |
| 11:00-13:00 | First end-to-end path working on the real brief |
| 13:00-17:00 | Build the actual product |
| 17:00-19:00 | Demo surface. Time-boxed, abandon at 19:00 |
| 19:00-21:00 | Rehearse, reconcile any cost ledger, record digests |
| **21:00** | **Feature freeze. Not negotiable** |

The C1 canary push moves to **Friday** now. There is no reason to spend event time pushing work that
was finished days earlier, and it guarantees a tagged, demoable commit exists before the brief is
even read.

## 8. What to prepare Friday, given all of this

1. Everything in `PREFLIGHT.md`, unchanged. The account checks still matter for T3.
2. **Push the canary branch and tag on Friday**, not Saturday morning.
2b. **Open Warp and paste `WARP_BOOTSTRAP.txt`.** Confirm the agent verifies the checkpoint and
    summarizes correctly before you trust it with a task. Run task 0 calibration from
    `WARP_TASKS.md` so you know your real credit burn before Saturday rather than during it.
3. Re-read `docs/RETARGETING.md`. It is the playbook for 09:30.
4. Verify T0: unplug the network, run the Autopsy demo, confirm it works. That is your floor and it
   costs two minutes to prove.
5. Rehearse the 40-second version out loud. Twice.
6. Sleep. The brief arrives at 09:00 and the first 30 minutes decide the day.
