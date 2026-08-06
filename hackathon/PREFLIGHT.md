# Preflight, Friday 2026-08-07

| Field | Value |
|---|---|
| Version | 1.0 |
| Prepared | 2026-08-05 |
| Do this on | Friday 2026-08-07, not Saturday morning |
| Owner | Arun. These are browser and console actions, not agent actions. |
| Time | About 45 minutes, plus the end-to-end rehearsal |

Doing this Friday is the single highest-leverage hour of the whole week. Every
item below that fails on Saturday morning costs you build time you cannot get
back, and account or billing problems are exactly the kind that cannot be fixed
by writing code faster.

## Part A: account and credentials

Do not paste an API key into a document, issue, fixture, chat, screenshot, or
shell history. No agent needs to see it.

- [ ] Open the SuperGrok usage page. Note whether an `API` category appears.
      Record yes or no. Do not assume it grants developer API credit.
- [ ] Sign in to `console.x.ai` with the same account.
- [ ] Select the team you intend to bill. Confirm which team it is.
- [ ] Read the API credit balance. Record the number.
- [ ] Read the postpaid limit and auto top-up state. Set postpaid to zero or to
      an approved low cap for the smoke test.
- [ ] Confirm `grok-imagine-image` and `grok-imagine-image-quality` are enabled
      for that team.
- [ ] Create a least-privilege key scoped to local development.
- [ ] Store it in your password manager or shell keychain. Not in the repo.
- [ ] Confirm `.env` is git-ignored: `git check-ignore -v .env`

**If the console shows no credit or no model access, stop and do not improvise.**
Continue entirely in fixture mode. The offline demo is a complete, honest story
by itself, and this outcome does not block Saturday. It only changes the pitch.

## Part B: one approved smoke call

The goal is not an image. The goal is the exact response shape, so Saturday's
implementation is transcription rather than discovery.

- [ ] Confirm the model-discovery endpoint responds with your key.
- [ ] Make **at most one** standard-model, 1K, non-sensitive generation call.
- [ ] Capture the complete raw response.
- [ ] Record, in `COST_LEDGER.md`: the actual `cost_in_usd_ticks`, the resolved
      model, the moderation field name and value, the request identifier, and
      whether output arrived as a URL or as base64.
- [ ] Record the exact JSON field names in the UNVERIFIED table of
      `COST_LEDGER.md`. That table is what unblocks `extract_provider_response`.
- [ ] Rotate or revoke the key afterwards if it touched any unsafe surface.

Expected cost of this step at the 2026-08-05 price snapshot: about $0.022.

## Part C: end-to-end rehearsal

- [ ] Fresh clone into a scratch directory. Prove the repository stands alone.
- [ ] Create the virtual environment and install from the lockfile.
- [ ] Run the three verification commands in `GROK_RUNBOOK.md` section 7.
- [ ] Confirm `448 passed, 2 xfailed`.
- [ ] Confirm the artifact digest matches.
- [ ] Rehearse the canary push end to end on a throwaway branch, then delete it.
      Confirm `gh` is authenticated and that the draft PR actually triggers CI.
- [ ] Walk the demo out loud once, timed. Three minutes.

## Part D: logistics

- [ ] Laptop charger, and a second one if you own it.
- [ ] Phone hotspot tested against the venue as a network fallback.
- [ ] The repository cloned and the venv built **before** you arrive. Venue wifi
      on the morning of a hackathon is not a dependency you want.
- [ ] Offline demo verified with wifi switched off. This is your floor.
- [ ] Teammate has the clone command from `CANARY_RELEASE.md` section 7.
- [ ] Ask the organizer about the theme if it is still unannounced.

## Part E: fatigue plan

You have a separate interview on Tuesday 2026-08-11. The build runs to 01:00 on
Sunday. Protect the Tuesday slot deliberately.

- [ ] Decide your hard stop now and write it down. 21:00 feature freeze.
- [ ] Sleep Friday night. A rested Saturday beats a prepared exhausted one.
- [ ] Food and water at the venue. Set a reminder rather than relying on hunger.
- [ ] Sunday is recovery. Schedule nothing.
- [ ] Monday is Tuesday's prep day, not a project day.
- [ ] Do not commit to post-hackathon follow-ups on Saturday night. Anything
      anyone asks for goes in a note and gets answered Monday.

## Preflight result

Fill this in Friday evening. If any line is unresolved, decide Friday what the
Saturday fallback is rather than discovering it at 09:00.

| Item | Result | Fallback if it failed |
|---|---|---|
| API category visible in SuperGrok | | |
| Team credit balance | | |
| Image models enabled | | |
| Scoped key created | | |
| Smoke call succeeded | | Fixture mode only |
| Response field names recorded | | Discover live on Saturday |
| Fresh clone reproduces 448 passed | | |
| Artifact digest matches | | |
| Canary push rehearsed | | |
| Offline demo works with wifi off | | This is the floor. It must pass. |
