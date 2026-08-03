"""Gradio Autopsy UI backed only by committed demo artifacts."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import gradio as gr

from adjacency.autopsy import (
    AutopsyBundle,
    AutopsyDataError,
    AutopsyDemo,
    AutopsyRecord,
    DemoFrame,
    GatePhase,
    audit_payload,
    load_autopsy_bundle,
    render_evidence_image,
)
from adjacency.contracts import DeltaKind

DEMO_MODE = "demo"
TABLE_HEADERS = ["Trace", "Decision", "Tier", "Signal"]

AUTOPSY_CSS = """
.gradio-container {
  --adj-gate-banner-background: #fff1f2;
  --adj-gate-banner-border: #b91c1c;
  --adj-gate-banner-text: #7f1d1d;
  --adj-mode-badge-background: #ecfdf5;
  --adj-mode-badge-border: #047857;
  --adj-mode-badge-text: #065f46;
  max-width: 1680px !important;
}
body.dark .gradio-container {
  --adj-gate-banner-background: #450a0a;
  --adj-gate-banner-border: #ef4444;
  --adj-gate-banner-text: #fecaca;
  --adj-mode-badge-background: #12372a;
  --adj-mode-badge-border: #2b7a55;
  --adj-mode-badge-text: #a7f3d0;
}
.autopsy-header {
  border-bottom: 1px solid var(--border-color-primary);
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
}
.mode-badge {
  background: var(--adj-mode-badge-background) !important;
  border: 1px solid var(--adj-mode-badge-border) !important;
  border-radius: 999px;
  color: var(--adj-mode-badge-text) !important;
  display: inline-block;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 0.35rem 0.65rem;
}
.delta-column {
  border: 1px solid var(--border-color-primary);
  border-radius: 12px;
  min-height: 430px;
  padding: 0.65rem;
}
.gate-banner {
  background: var(--adj-gate-banner-background) !important;
  border: 1px solid var(--adj-gate-banner-border) !important;
  border-radius: 10px;
  color: var(--adj-gate-banner-text) !important;
  padding: 0.65rem 0.9rem;
}
.gate-banner h2 {
  color: var(--adj-gate-banner-text) !important;
}
#gate-fail-row button {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  text-align: left;
  white-space: normal;
}
.source-note {
  color: var(--body-text-color-subdued);
  font-size: 0.78rem;
}
"""

AUTOPSY_THEME = gr.themes.Base(primary_hue="red", neutral_hue="slate")


class UIModeError(ValueError):
    """Raised when an unsupported UI execution mode is requested."""


def ui_mode() -> str:
    mode = os.environ.get("ADJ_UI_MODE", DEMO_MODE).strip().lower() or DEMO_MODE
    if mode != DEMO_MODE:
        raise UIModeError("ADJ_UI_MODE currently supports only demo")
    return mode


def create_app(
    *,
    root: Path | str | None = None,
    step_delay_seconds: float = 0.06,
) -> gr.Blocks:
    """Build the offline-first Autopsy interface."""

    ui_mode()
    if step_delay_seconds < 0:
        raise ValueError("step delay cannot be negative")
    repo_root = Path(root).resolve() if root else Path(__file__).resolve().parents[2]
    bundle = load_autopsy_bundle(repo_root)
    demo = AutopsyDemo(bundle)
    initial_frame = demo.frames()[0]
    initial_state = _state(initial_frame)

    with gr.Blocks(
        fill_width=True,
        title="Adjacency Autopsy",
    ) as app:
        frame_state = gr.State(initial_state)
        with gr.Row(elem_classes="autopsy-header"):
            with gr.Column(scale=4):
                gr.Markdown(
                    "# Adjacency Autopsy\n"
                    "Compare the compiled policy engine with the same-prose keyword baseline."
                )
            with gr.Column(scale=2, min_width=300):
                gr.HTML('<span class="mode-badge">DEMO MODE · FROZEN CORPUS · NO API KEY</span>')
                gr.Markdown(
                    f"**{len(bundle.records)} verified items** · "
                    f"**{sum(record.item.has_media for record in bundle.records)} local media**\n\n"
                    '<span class="source-note">Source: `corpus/frozen/manifest.json`</span>'
                )

        with gr.Row():
            run_button = gr.Button("Run Autopsy", variant="primary", scale=3)
            reset_button = gr.Button("Reset", variant="secondary", scale=1)

        gate_banner = gr.Markdown(visible=False, elem_classes="gate-banner")

        with gr.Row(equal_height=True):
            with gr.Column(elem_classes="delta-column"):
                gr.Markdown("## AGREE\nBoth systems make the same delivery decision.")
                agree_table = _table("Agreement traces")
            with gr.Column(elem_classes="delta-column"):
                gr.Markdown("## OVER_BLOCK\nThe blocklist withholds safe inventory.")
                over_counter = gr.Markdown(_counter(bundle, 0))
                over_table = _table("Recovered inventory traces")
            with gr.Column(elem_classes="delta-column"):
                gr.Markdown("## UNDER_BLOCK\nThe blocklist serves inventory the engine withholds.")
                gate_fail_row = gr.Button(
                    "GATE FAIL · G1_SPAN_NOT_FOUND",
                    variant="stop",
                    visible=False,
                    elem_id="gate-fail-row",
                )
                under_table = _table("Caught-risk traces")

        with gr.Row():
            with gr.Column(scale=3):
                item_detail = gr.Markdown(
                    "### Evidence inspector\nSelect a table row to inspect its source evidence."
                )
                evidence_image = gr.Image(
                    label="Cited media region",
                    type="pil",
                    interactive=False,
                    height=460,
                )
            with gr.Column(scale=2):
                with gr.Accordion("Audit drawer", open=True, elem_classes="audit-drawer"):
                    audit_json = gr.JSON(
                        label="Structured trace and full gate chain",
                        open=False,
                        height=520,
                    )
                gr.Markdown("### Human review queue")
                hitl_table = gr.Dataframe(
                    value=[],
                    headers=["Trace", "Action", "Reason"],
                    datatype=["str", "str", "str"],
                    type="array",
                    interactive=False,
                    row_count=0,
                    column_count=3,
                    max_height=280,
                    wrap=True,
                    show_row_numbers=False,
                )

        gr.Markdown(
            "Artifact paths: `artifacts/ui/autopsy_snapshot.json`, "
            "`artifacts/wednesday/judge_traces.json`, "
            "`artifacts/tuesday/baseline_blocklist.json`, and "
            "`corpus/frozen/manifest.json`. The dollar counter uses an illustrative input from "
            "`artifacts/ui/economics_assumption.json`, not measured revenue."
        )

        run_event = run_button.click(
            fn=_runner(demo, bundle, step_delay_seconds),
            inputs=None,
            outputs=[
                frame_state,
                agree_table,
                over_table,
                over_counter,
                under_table,
                gate_fail_row,
                gate_banner,
                hitl_table,
            ],
            show_progress="hidden",
        )
        reset_button.click(
            fn=lambda: (
                initial_state,
                [],
                [],
                _counter(bundle, 0),
                [],
                gr.update(visible=False),
                gr.update(value=None, visible=False),
                [],
                "### Evidence inspector\nSelect a table row to inspect its source evidence.",
                None,
                None,
            ),
            inputs=None,
            outputs=[
                frame_state,
                agree_table,
                over_table,
                over_counter,
                under_table,
                gate_fail_row,
                gate_banner,
                hitl_table,
                item_detail,
                evidence_image,
                audit_json,
            ],
            cancels=[run_event],
            queue=False,
        )

        detail_outputs = [item_detail, evidence_image, audit_json]
        agree_table.select(
            fn=_table_selector(demo, bundle, DeltaKind.AGREE),
            inputs=[frame_state],
            outputs=detail_outputs,
            show_progress="hidden",
        )
        over_table.select(
            fn=_table_selector(demo, bundle, DeltaKind.OVER_BLOCK),
            inputs=[frame_state],
            outputs=detail_outputs,
            show_progress="hidden",
        )
        under_table.select(
            fn=_table_selector(demo, bundle, DeltaKind.UNDER_BLOCK),
            inputs=[frame_state],
            outputs=detail_outputs,
            show_progress="hidden",
        )
        gate_fail_row.click(
            fn=lambda: _inspect(bundle.record(bundle.wow_item_id)),
            inputs=None,
            outputs=detail_outputs,
            show_progress="hidden",
        )

    return app.queue(default_concurrency_limit=2)


def _table(label: str) -> gr.Dataframe:
    return gr.Dataframe(
        value=[],
        headers=TABLE_HEADERS,
        datatype=["str", "str", "str", "str"],
        type="array",
        label=label,
        interactive=False,
        row_count=0,
        column_count=len(TABLE_HEADERS),
        max_height=360,
        wrap=True,
        column_widths=["26%", "25%", "16%", "33%"],
        show_row_numbers=False,
    )


def _runner(
    demo: AutopsyDemo,
    bundle: AutopsyBundle,
    step_delay_seconds: float,
) -> Callable[[], Iterator[tuple[object, ...]]]:
    def run() -> Iterator[tuple[object, ...]]:
        for frame in demo.frames():
            view = demo.view(frame)
            yield (
                _state(frame),
                _rows(view.agree),
                _rows(view.over_block),
                _counter(bundle, len(view.over_block)),
                _rows(view.under_block),
                _gate_button(view.gate_fail),
                _gate_banner(view.gate_fail),
                _hitl_rows(view.hitl),
            )
            if step_delay_seconds:
                time.sleep(step_delay_seconds)

    return run


def _table_selector(
    demo: AutopsyDemo,
    bundle: AutopsyBundle,
    kind: DeltaKind,
) -> Callable[[dict[str, object], gr.SelectData], tuple[object, ...]]:
    def select(state: dict[str, object], event: gr.SelectData) -> tuple[object, ...]:
        view = demo.view(_frame(state))
        records = {
            DeltaKind.AGREE: view.agree,
            DeltaKind.OVER_BLOCK: view.over_block,
            DeltaKind.UNDER_BLOCK: view.under_block,
        }[kind]
        row_index = _row_index(event.index)
        if row_index < 0 or row_index >= len(records):
            return (
                "### Evidence inspector\nThe selected row is no longer visible.",
                None,
                {"error": "stale row selection"},
            )
        return _inspect(bundle.record(records[row_index].item.item_id))

    return select


def _inspect(record: AutopsyRecord) -> tuple[object, ...]:
    verdict = record.trace.final_verdict
    evidence = verdict.evidence
    evidence_note = "No cited evidence."
    if evidence:
        evidence_note = "Evidence: " + ", ".join(
            _clean(getattr(item, "quote", "") or getattr(item, "note", "")) for item in evidence
        )
    detail = (
        f"### {record.trace_id}\n"
        f"**{record.delta.kind.value}** · baseline **{record.baseline.action.value}** · "
        f"engine **{verdict.action.value}** · Tier {verdict.tier}\n\n"
        f"{_clean(record.item.text)}\n\n"
        f"{evidence_note}\n\n"
        f"[Open source post]({record.source_url})"
    )
    return detail, render_evidence_image(record), _clean_object(audit_payload(record))


def _rows(records: Sequence[AutopsyRecord]) -> list[list[str]]:
    return [
        [
            record.trace_id,
            f"{record.baseline.action.value} → {record.trace.final_verdict.action.value}",
            f"T{record.trace.final_verdict.tier}",
            _signal(record),
        ]
        for record in records
    ]


def _signal(record: AutopsyRecord) -> str:
    if record.trace.failed_gate_codes:
        return "GATE FAIL · " + ", ".join(record.trace.failed_gate_codes)
    if record.baseline.matched_terms:
        return "Matched: " + ", ".join(record.baseline.matched_terms[:3])
    if record.trace.escalation_reasons:
        return "Escalated: " + ", ".join(record.trace.escalation_reasons[:2])
    return _clean(record.trace.final_verdict.rationale)[:110]


def _hitl_rows(records: Sequence[AutopsyRecord]) -> list[list[str]]:
    return [
        [
            record.trace_id,
            record.trace.final_verdict.action.value,
            ", ".join(record.trace.failed_gate_codes) or "policy review",
        ]
        for record in records
    ]


def _counter(bundle: AutopsyBundle, over_block_count: int) -> str:
    value = _money(
        Decimal(over_block_count) * bundle.economics.default_value_per_recovered_item_usd
    )
    per_item = _money(bundle.economics.default_value_per_recovered_item_usd)
    return (
        f"### ${value}\n"
        f"Illustrative recovered-spend counter · {over_block_count} items × ${per_item}\n\n"
        "Source: `artifacts/ui/economics_assumption.json`"
    )


def _gate_button(record: AutopsyRecord | None):
    if record is None:
        return gr.update(visible=False)
    return gr.update(
        value=(
            f"GATE FAIL · G1_SPAN_NOT_FOUND · {record.trace_id} · "
            f"{record.pre_gate_action.value} → {record.trace.final_verdict.action.value} · Inspect"
        ),
        visible=True,
    )


def _gate_banner(record: AutopsyRecord | None):
    if record is None:
        return gr.update(value=None, visible=False)
    return gr.update(
        value=(
            "## GATE FAIL: G1_SPAN_NOT_FOUND\n"
            f"`{record.trace_id}` changed from **{record.pre_gate_action.value}** to "
            f"**{record.trace.final_verdict.action.value}** and entered human review."
        ),
        visible=True,
    )


def _state(frame: DemoFrame) -> dict[str, object]:
    return {
        "gate_phase": frame.gate_phase.value,
        "visible_item_ids": list(frame.visible_item_ids),
    }


def _frame(state: dict[str, object]) -> DemoFrame:
    try:
        item_ids = tuple(str(item_id) for item_id in state["visible_item_ids"])
        phase = GatePhase(str(state["gate_phase"]))
    except (KeyError, TypeError, ValueError) as error:
        raise AutopsyDataError("UI frame state is invalid") from error
    return DemoFrame(item_ids, phase)


def _row_index(index: Any) -> int:
    if isinstance(index, (list, tuple)):
        index = index[0] if index else -1
    return int(index)


def _money(value: Decimal) -> str:
    try:
        return format(value.quantize(Decimal("0.01")), ",.2f")
    except (InvalidOperation, ValueError) as error:
        raise AutopsyDataError("invalid economics value") from error


def _clean(value: str) -> str:
    return value.replace(chr(0x2014), ". ")


def _clean_object(value: object) -> object:
    if isinstance(value, str):
        return _clean(value)
    if isinstance(value, dict):
        return {key: _clean_object(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_object(item) for item in value]
    return value
