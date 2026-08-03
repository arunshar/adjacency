# Adjacency Results Sheet

This sheet contains only observed results that have a committed evidence path. It separates what was measured from what should not be inferred.

| Question | Observed result | Evidence path | What it supports |
|---|---|---|---|
| Do deterministic gates catch seeded structural faults? | 12/12 injected faults caught with 0/4 clean cases rejected. | `artifacts/tuesday/synthetic_faults.json` | The seeded gate harness detects every injected failure in this evaluation without rejecting the unmodified controls. |
| Is raw-prompt evidence grounded? | 68% grounding failure in raw-prompt run 1. | `evals/prompt_baseline/comparison.json` | A free-form verdict frequently returns offsets that do not reproduce its quoted source text on this frozen run. |
| Are identical-input raw-prompt actions stable? | 2% action disagreement across the recorded runs. | `evals/prompt_baseline/comparison.json` | The action can change across identical inputs even when the policy and corpus are fixed. |
| How much work reaches the strongest reasoning tier? | 44% of frozen decisions escalated to Tier 2. | `artifacts/wednesday/judge_report.json` | The recorded ladder is closer to bimodal than smooth. Tier 1 absorbs only a narrow residual in this run. |
| What did the measured judge route cost? | $6.12 per 1,000 decisions. | `artifacts/wednesday/judge_report.json` | The value is the rounded blended cost computed from recorded per-call usage for this frozen run. |
| Does the optional durable review path work against Temporal Cloud? | Yes. The proof records a pending-state query, an adjudication signal, an adjudicated-state query, and workflow completion. | `artifacts/temporal/hitl_live_proof.json` | The optional queue adapter completed a real cloud protocol round-trip. The proof action is an integration event, not a human label. |

## Reading rules

- The synthetic-fault result is not an estimate of production incident recall.
- The raw-prompt percentages describe the recorded frozen evaluation. They are not universal model rates.
- The routing and cost values are measurements, not accuracy evidence.
- The Temporal artifact proves protocol behavior. It does not prove adjudicator quality.
- The Autopsy dollar counter is excluded because it is illustrative. Its assumption is stored in `artifacts/ui/economics_assumption.json`.

## Reproduction entry points

```bash
PYTHONPATH=src .venv/bin/python scripts/build_tuesday_artifacts.py
PYTHONPATH=src .venv/bin/python scripts/freeze_wednesday_corpus.py
PYTHONPATH=src .venv/bin/python scripts/run_wednesday_evals.py
PYTHONPATH=src .venv/bin/python scripts/build_ui_artifacts.py
```

The Temporal proof script is `scripts/prove_temporal_hitl.py`. It requires an explicitly selected Temporal backend and valid credentials. The public demo does not run it.
