# Judging Map

No formal Grokathon scoring rubric is stored in this repository at freeze. The dimensions below are an explicit presentation map, not a claim about unpublished judging criteria.

| Likely question | What to show | Evidence |
|---|---|---|
| Is the problem important to X? | Brand safety sits at the boundary between advertiser intent and the post beside an ad. Open with the control gap between lexical matching and joint text-image context. | `paper/main.tex`, `slides/adjacency_deck_portable.html` |
| Is the system genuinely xAI-native? | Grok structured outputs compile the policy and judge residual inventory. Recorded xAI response fixtures make every live surface replayable. | `src/adjacency/policy.py`, `src/adjacency/judge.py`, `src/adjacency/xai.py`, `fixtures/api/` |
| Is this more than a prompt wrapper? | Show typed contracts, compile-time G0, per-verdict G1 through G6, content hashes, and the same-prose keyword baseline. | `src/adjacency/contracts.py`, `src/adjacency/gates.py`, `artifacts/tuesday/policy_spec.json`, `artifacts/tuesday/baseline_blocklist.json` |
| Does the demo have a clear visual beat? | Run the Autopsy, open the `G1_SPAN_NOT_FOUND` item, expand the cited image region, and reveal the audit drawer. | `artifacts/ui/autopsy_snapshot.json`, `slides/autopsy_gate.png`, `artifacts/demo/adjacency_fallback.mp4` |
| Is there evaluation evidence? | Present the one-page table. Lead with 12/12 seeded faults caught and 0/4 clean cases rejected, then the 68% raw-prompt grounding failure and 2% action disagreement. | `RESULTS.md`, `artifacts/tuesday/synthetic_faults.json`, `evals/prompt_baseline/comparison.json` |
| Is reasoning cost controlled? | Show the measured ladder honestly as bimodal, with 44% at Tier 2 and $6.12 per 1,000 decisions. Do not draw a smooth cascade. | `artifacts/wednesday/judge_report.json`, `slides/adjacency_deck.pdf` |
| What happens when the system is uncertain? | A deterministic gate changes the delivery disposition to `REVIEW`. The default queue is local and the optional Temporal path has a real cloud round-trip. | `src/adjacency/gates.py`, `src/adjacency/hitl.py`, `artifacts/temporal/hitl_live_proof.json` |
| Can the demo survive venue connectivity? | The public Space and local demo replay frozen artifacts. The fallback video captures the complete successful run. Neither path requires xAI or Temporal. | `deploy/huggingface/stage.sh`, `artifacts/demo/adjacency_fallback.json` |
| Is there a credible rollout path? | Keep the product read-only first, then run shadow evaluation, then activate individual clauses only after independent labels support them. | `paper/main.tex`, `slides/_deck_data.json` |

## Demo order

1. State the through-line: Spatial Atlas discipline applied to brand-safety policy.
2. Run the offline Autopsy.
3. Contrast `OVER_BLOCK` with `UNDER_BLOCK`.
4. Open the `G1_SPAN_NOT_FOUND` row and show the forced move to `REVIEW`.
5. Show the evidence image and audit chain.
6. Put the results sheet on screen with every value beside its path.
7. Close with the real Temporal protocol proof and the staged rollout.

## Claims to avoid

- Do not call the synthetic-fault result production recall.
- Do not call the raw-prompt rates universal Grok behavior.
- Do not call the blended cost a pricing guarantee.
- Do not call the Temporal proof a human label.
- Do not present the illustrative dollar counter as recovered revenue.
- Do not describe Anyscale as part of the frozen build. It remains a separately gated hackathon-day Tier-0.5 item.
