# Pull request

## Summary

What changed and why?

## Checklist

- [ ] `ruff check src tests` and `ruff format --check src tests` are clean.
- [ ] `pytest -m "not e2e" --cov --cov-fail-under=90` is clean.
- [ ] No gate function calls a model, opens a socket, reads an unhanded clock, or touches the filesystem.
- [ ] No code path reads `Verdict.rationale` to decide anything. It is display-only.
- [ ] Every new failure branch resolves to `REVIEW` or `BLOCK`, never `ALLOW`.
- [ ] If a gate changed, every new branch has its own test and the gate modules are still at 100 percent.
- [ ] If a gate code string changed, it was added rather than reworded. Codes are API.
- [ ] If an evidence type was added, it has a test containing an emoji.
- [ ] `src/adjacency/contracts.py` and `gates.py` still import nothing from the `[model]` extra.
- [ ] Every number in the diff, including in docstrings and this description, is reproducible by a named command or artifact path.
