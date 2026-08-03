# Contributing

## Before you push

```bash
ruff check src tests && ruff format --check src tests
pytest -m "not e2e" --cov --cov-fail-under=90
```

CI runs the same commands plus `pip-audit` and `bandit`. If it is green locally it should be green
there.

## Hard invariants

These are the rules that a passing test suite will not catch on its own. Breaking one is a bug even
when everything is green.

1. **The rationale is display-only.** No gate, and no code path that produces a decision, may read
   `Verdict.rationale`. Decisions come from `action`, `severity`, `clause_ids`, and `evidence`. If you
   find yourself parsing prose to decide something, the design has leaked.

2. **Gates are pure.** No gate function may call a model, open a socket, read a clock it was not
   handed, or touch the filesystem. They are total functions over already-computed structures, and
   that is what makes the audit reproducible.

3. **Fail closed, always toward not serving.** Every new failure branch resolves to `REVIEW` or
   `BLOCK`, never `ALLOW`. If a gate has a path that can turn a `BLOCK` into an `ALLOW`, that path
   needs a logged human approval (see G3) or it does not ship.

4. **The deterministic core stays free of model dependencies.** `src/adjacency/contracts.py` and
   `src/adjacency/gates.py` import nothing from the `[model]` extra. CI has a dedicated job that
   installs without it and asserts `litellm`, `httpx`, and `PIL` are not importable.

5. **New gate, new exhaustive test.** Every failure branch of every gate has its own test. The gate
   modules are held to 100 percent line and branch coverage, not the package floor of 90.

6. **Gate codes are API.** `G1_SPAN_NOT_FOUND` and its siblings appear in the audit ledger and on
   screen. Renaming one is a breaking change. Add a new code rather than reword an existing one.

7. **Text spans are character offsets into NFC-normalized text.** Not bytes, not UTF-16 code units.
   If you add an evidence type, it follows the same rule, and it gets a test with an emoji in it.

## Adding a gate

Gates are numbered and the numbering is stable. A new gate gets the next number, a pure function in
`gates.py`, a stable `GATE_N_REASON` code, an entry in the README table, and its own test section
covering every branch. If it applies per verdict, wire it into `run_verdict_gates` and confirm the
strictest-coercion ordering still holds.

## Numbers

Any number that reaches a README, a docstring, or a commit message must be reproducible by a command
someone else can run. Cite the command or the artifact path next to it. "Roughly" and "about" are
fine; unsourced precision is not.
