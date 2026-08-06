"""Read-only Gradio surface for the frozen ImagineSignal offline demo.

Loads committed artifact JSON and content-addressed fixture PNGs only. Never
calls a provider, never regenerates fixtures, and never writes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gradio as gr

from adjacency.imagine_signal.demo import (
    CONTROL_ID,
    COOL_ID,
    WARM_ID,
    build_demo_request,
)

DEMO_MODE = "demo"
ARTIFACT_RELATIVE = Path("artifacts") / "imagine_signal" / "offline_demo.json"
ASSET_DIR_RELATIVE = Path("fixtures") / "imagine_signal" / "assets"

GATE_TITLES: dict[str, str] = {
    "IS0": "request budget",
    "IS1": "lineage",
    "IS2": "controlled mutation",
    "IS3": "provider admission",
    "IS4": "asset integrity",
    "IS5": "outcome admission",
    "IS6": "statistical validity",
    "IS7": "auction sensitivity",
    "IS8": "evidence-to-action ceiling",
}

ROLE_BY_CREATIVE_ID: dict[str, str] = {
    CONTROL_ID: "control",
    WARM_ID: "variant",
    COOL_ID: "variant",
}


class ImagineSignalUIError(ValueError):
    """Raised when the frozen ImagineSignal demo surface cannot be built."""


@dataclass(frozen=True, slots=True)
class FamilyMemberView:
    """One control or variant card backed by frozen bytes."""

    creative_id: str
    role: str
    image_path: Path
    media_sha256: str
    cost_in_usd_ticks: int
    cost_status: str
    mutation_id: str | None
    changed_axis: str | None
    changed_level: str | None
    state: str
    provider: str


@dataclass(frozen=True, slots=True)
class GateView:
    """One IS0-IS8 ladder row from the receipt."""

    gate: str
    title: str
    code: str
    passed: bool
    coerce_to: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class ImagineSignalView:
    """Everything the read-only surface needs, derived from frozen inputs."""

    artifact_path: Path
    family: tuple[FamilyMemberView, ...]
    changed_axis: str
    locked_attributes: tuple[str, ...]
    gate_ladder: tuple[GateView, ...]
    final_action: str
    proposed_action: str
    evidence_class: str
    claim_wording: str
    rationale: str
    explanation: str
    cost_total_ticks: int
    cost_status: str
    per_generation_costs: tuple[tuple[str, int, str], ...]
    run_mode: str
    network_used: bool
    provider_call_used: bool
    production_authorization: str
    prohibited_claims: tuple[str, ...]
    receipt_sha256: str
    artifact_sha256: str
    efficiency_note: str
    raw_decision: dict[str, Any]
    raw_receipt: dict[str, Any]


def ui_mode() -> str:
    mode = os.environ.get("ADJ_UI_MODE", DEMO_MODE).strip().lower() or DEMO_MODE
    if mode != DEMO_MODE:
        raise ImagineSignalUIError("ADJ_UI_MODE currently supports only demo")
    return mode


def load_imagine_signal_view(root: Path | str | None = None) -> ImagineSignalView:
    """Load the committed offline artifact and fixture PNGs into a view model."""

    ui_mode()
    repo_root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[3]
    artifact_path = repo_root / ARTIFACT_RELATIVE
    try:
        raw_text = artifact_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ImagineSignalUIError(
            f"cannot read ImagineSignal artifact: {artifact_path}"
        ) from error
    try:
        artifact = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ImagineSignalUIError(
            f"ImagineSignal artifact is not valid JSON: {artifact_path}"
        ) from error
    if not isinstance(artifact, dict):
        raise ImagineSignalUIError("ImagineSignal artifact root must be an object")

    request = build_demo_request(repo_root)
    mutation_by_id = {mutation.mutation_id: mutation for mutation in request.mutations}
    if not request.mutations:
        raise ImagineSignalUIError("demo request has no mutations")
    changed_axis = request.mutations[0].axis
    if any(mutation.axis != changed_axis for mutation in request.mutations):
        raise ImagineSignalUIError("demo family must share one mutation axis")
    locked_attributes = tuple(
        sorted(locked.name for locked in request.mutations[0].locked_attributes)
    )

    assets = artifact.get("assets")
    if not isinstance(assets, list) or len(assets) != 3:
        raise ImagineSignalUIError("ImagineSignal artifact must carry exactly three assets")

    family_members: list[FamilyMemberView] = []
    per_generation: list[tuple[str, int, str]] = []
    asset_dir = repo_root / ASSET_DIR_RELATIVE
    for asset in assets:
        if not isinstance(asset, dict):
            raise ImagineSignalUIError("asset entries must be objects")
        creative_id = str(asset.get("creative_id") or "")
        media_sha256 = str(asset.get("media_sha256") or "")
        if not creative_id or len(media_sha256) != 64:
            raise ImagineSignalUIError("asset is missing creative_id or media_sha256")
        image_path = asset_dir / f"{media_sha256}.png"
        if not image_path.is_file():
            raise ImagineSignalUIError(f"missing fixture image for {creative_id}: {image_path}")
        mutation_id = asset.get("mutation_id")
        mutation_id_str = str(mutation_id) if mutation_id else None
        changed_level = None
        axis_for_member = None
        if mutation_id_str is not None:
            mutation = mutation_by_id.get(mutation_id_str)
            if mutation is None:
                raise ImagineSignalUIError(
                    f"artifact mutation_id not in demo request: {mutation_id_str}"
                )
            changed_level = mutation.level
            axis_for_member = mutation.axis
        try:
            cost_ticks = int(asset["cost_in_usd_ticks"])
        except (KeyError, TypeError, ValueError) as error:
            raise ImagineSignalUIError(f"invalid cost_in_usd_ticks for {creative_id}") from error
        cost_status = str(asset.get("cost_status") or "")
        if not cost_status:
            raise ImagineSignalUIError(f"missing cost_status for {creative_id}")
        family_members.append(
            FamilyMemberView(
                creative_id=creative_id,
                role=ROLE_BY_CREATIVE_ID.get(creative_id, "member"),
                image_path=image_path,
                media_sha256=media_sha256,
                cost_in_usd_ticks=cost_ticks,
                cost_status=cost_status,
                mutation_id=mutation_id_str,
                changed_axis=axis_for_member,
                changed_level=changed_level,
                state=str(asset.get("state") or ""),
                provider=str(asset.get("provider") or ""),
            )
        )
        per_generation.append((creative_id, cost_ticks, cost_status))

    decision = artifact.get("decision")
    receipt = artifact.get("receipt")
    if not isinstance(decision, dict) or not isinstance(receipt, dict):
        raise ImagineSignalUIError("artifact is missing decision or receipt objects")

    gate_source = receipt.get("gate_results") or decision.get("gate_results")
    if not isinstance(gate_source, list) or len(gate_source) != 9:
        raise ImagineSignalUIError("receipt must carry nine IS0-IS8 gate results")
    gate_ladder = tuple(_gate_view(entry) for entry in gate_source)

    try:
        cost_total_ticks = int(receipt["cost_total_ticks"])
    except (KeyError, TypeError, ValueError) as error:
        raise ImagineSignalUIError("receipt is missing cost_total_ticks") from error
    cost_status = str(receipt.get("cost_status") or "")
    if not cost_status:
        raise ImagineSignalUIError("receipt is missing cost_status")

    efficiency = artifact.get("efficiency") if isinstance(artifact.get("efficiency"), dict) else {}
    efficiency_note = (
        f"Evidence class `{efficiency.get('evidence_class', 'unknown')}` on cost basis "
        f"`{efficiency.get('cost_basis', 'unknown')}`. The three-of-three versus two-of-three "
        "comparison is a fixture-backed pipeline check, not measured provider efficiency."
    )

    prohibited = artifact.get("prohibited_claims") or ()
    if not isinstance(prohibited, list):
        raise ImagineSignalUIError("prohibited_claims must be a list")

    return ImagineSignalView(
        artifact_path=artifact_path,
        family=tuple(family_members),
        changed_axis=changed_axis,
        locked_attributes=locked_attributes,
        gate_ladder=gate_ladder,
        final_action=str(receipt.get("final_action") or decision.get("final_action") or ""),
        proposed_action=str(
            receipt.get("proposed_action") or decision.get("proposed_action") or ""
        ),
        evidence_class=str(receipt.get("evidence_class") or decision.get("evidence_class") or ""),
        claim_wording=str(receipt.get("claim_wording") or decision.get("claim_wording") or ""),
        rationale=str(decision.get("rationale") or ""),
        explanation=str(artifact.get("explanation") or ""),
        cost_total_ticks=cost_total_ticks,
        cost_status=cost_status,
        per_generation_costs=tuple(per_generation),
        run_mode=str(artifact.get("run_mode") or ""),
        network_used=bool(artifact.get("network_used")),
        provider_call_used=bool(artifact.get("provider_call_used")),
        production_authorization=str(artifact.get("production_authorization") or ""),
        prohibited_claims=tuple(str(item) for item in prohibited),
        receipt_sha256=str(receipt.get("receipt_sha256") or ""),
        artifact_sha256=str(artifact.get("artifact_sha256") or ""),
        efficiency_note=efficiency_note,
        raw_decision=dict(decision),
        raw_receipt=dict(receipt),
    )


def _gate_view(entry: object) -> GateView:
    if not isinstance(entry, dict):
        raise ImagineSignalUIError("gate result must be an object")
    gate = str(entry.get("gate") or "")
    if gate not in GATE_TITLES:
        raise ImagineSignalUIError(f"unknown gate id: {gate}")
    coerce = entry.get("coerce_to")
    return GateView(
        gate=gate,
        title=GATE_TITLES[gate],
        code=str(entry.get("code") or ""),
        passed=bool(entry.get("passed")),
        coerce_to=str(coerce) if coerce is not None else None,
        detail=str(entry.get("detail") or ""),
    )


def render_imagine_signal_panel(view: ImagineSignalView) -> None:
    """Render the read-only ImagineSignal panel into the current Gradio Blocks context."""

    with gr.Row(elem_classes="autopsy-header"):
        with gr.Column(scale=4):
            gr.Markdown(
                "# ImagineSignal\n"
                "Frozen offline replay of one approved control and two one-axis variants. "
                "The product output is the decision receipt, not the images."
            )
        with gr.Column(scale=2, min_width=300):
            gr.HTML(
                '<span class="mode-badge">DEMO MODE · FROZEN REPLAY · NO API KEY · READ ONLY</span>'
            )
            gr.Markdown(
                f"**run_mode `{view.run_mode}`** · "
                f"**network_used `{str(view.network_used).lower()}`** · "
                f"**provider_call_used `{str(view.provider_call_used).lower()}`**\n\n"
                f'<span class="source-note">Source: `{_display_path(view.artifact_path)}`</span>'
            )

    gr.Markdown(_summary_markdown(view))

    with gr.Row(equal_height=True):
        for member in view.family:
            with gr.Column(elem_classes="delta-column"):
                gr.Markdown(_member_heading(member, view.changed_axis))
                gr.Image(
                    value=str(member.image_path),
                    label=member.creative_id,
                    type="filepath",
                    interactive=False,
                    height=220,
                )
                gr.Markdown(_member_body(member))

    with gr.Row(equal_height=True):
        with gr.Column(elem_classes="delta-column"):
            gr.Markdown("## Changed attribute\nExactly one declared visual axis moves per variant.")
            gr.Markdown(
                f"**Axis:** `{view.changed_axis}`\n\n"
                + "\n".join(
                    f"- `{member.creative_id}`: level **{member.changed_level}**"
                    if member.changed_level
                    else f"- `{member.creative_id}`: control (no mutation)"
                    for member in view.family
                )
            )
        with gr.Column(elem_classes="delta-column"):
            gr.Markdown("## Locked attributes\nVerified byte-identical across the family.")
            gr.Markdown("\n".join(f"- `{name}`" for name in view.locked_attributes))
        with gr.Column(elem_classes="delta-column"):
            gr.Markdown("## Cost (from artifact)\nExact ticks only when the fixture reports them.")
            gr.Markdown(_cost_markdown(view))

    gr.Markdown("## Gate ladder `IS0` through `IS8`")
    gr.Dataframe(
        value=_gate_rows(view.gate_ladder),
        headers=["Gate", "Title", "Result", "Code", "Coercion"],
        datatype=["str", "str", "str", "str", "str"],
        type="array",
        label="ImagineSignal gates",
        interactive=False,
        row_count=9,
        column_count=5,
        wrap=True,
        max_height=360,
        show_row_numbers=False,
    )

    banner = _decision_banner(view)
    gr.Markdown(banner, elem_classes="gate-banner" if view.final_action != "TEST" else None)

    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown(
                "### Decision receipt\n"
                f"**Final action:** `{view.final_action}`  \n"
                f"**Proposed action:** `{view.proposed_action}`  \n"
                f"**Evidence class that permitted it:** `{view.evidence_class}`  \n"
                f"**Production authorization:** `{view.production_authorization}`\n\n"
                f"**Claim wording:** {view.claim_wording}\n\n"
                f"**Rationale:** {view.rationale}\n\n"
                f"**Explanation:** {view.explanation}"
            )
            gr.Markdown("### Claims this surface will not make")
            gr.Markdown("\n".join(f"- {claim}" for claim in view.prohibited_claims))
            gr.Markdown(f"### Efficiency note\n{view.efficiency_note}")
        with gr.Column(scale=2):
            with gr.Accordion("Receipt and decision JSON", open=False, elem_classes="audit-drawer"):
                gr.JSON(
                    value={
                        "decision": view.raw_decision,
                        "receipt": {
                            key: view.raw_receipt.get(key)
                            for key in (
                                "receipt_id",
                                "receipt_sha256",
                                "final_action",
                                "proposed_action",
                                "evidence_class",
                                "cost_status",
                                "cost_total_ticks",
                                "claim_wording",
                                "gate_results",
                            )
                        },
                        "artifact_sha256": view.artifact_sha256,
                    },
                    label="Frozen decision slice",
                    open=False,
                    height=520,
                )

    gr.Markdown(
        "Artifact paths: `artifacts/imagine_signal/offline_demo.json` and "
        "`fixtures/imagine_signal/assets/<media_sha256>.png`. "
        "This tab never generates, never spends, and never opens a provider connection. "
        f"Receipt digest `{view.receipt_sha256[:16]}...` · "
        f"artifact digest `{view.artifact_sha256[:16]}...`."
    )


def create_imagine_signal_app(*, root: Path | str | None = None) -> gr.Blocks:
    """Build a standalone Blocks app for the ImagineSignal demo tab content."""

    view = load_imagine_signal_view(root)
    with gr.Blocks(fill_width=True, title="ImagineSignal") as app:
        render_imagine_signal_panel(view)
    return app.queue(default_concurrency_limit=1)


def _summary_markdown(view: ImagineSignalView) -> str:
    locked = ", ".join(f"`{name}`" for name in view.locked_attributes)
    return (
        f"Controlled family from frozen fixtures: **control plus two variants**. "
        f"The only declared change is **`{view.changed_axis}`**. "
        f"Locked and held fixed: {locked}."
    )


def _member_heading(member: FamilyMemberView, axis: str) -> str:
    if member.role == "control":
        return f"## Control\n`{member.creative_id}`"
    level = member.changed_level or "?"
    return f"## Variant · {level}\n`{member.creative_id}` · axis `{axis}`"


def _member_body(member: FamilyMemberView) -> str:
    change_line = (
        f"Changed: `{member.changed_axis}` = **{member.changed_level}**"
        if member.changed_level
        else "Changed: none (approved control)"
    )
    return (
        f"{change_line}\n\n"
        f"Cost: **{member.cost_in_usd_ticks}** ticks · status `{member.cost_status}`\n\n"
        f"State `{member.state}` · provider `{member.provider}`\n\n"
        f'<span class="source-note">media_sha256 `{member.media_sha256[:16]}...`</span>'
    )


def _cost_markdown(view: ImagineSignalView) -> str:
    lines = [
        f"**Family total:** `{view.cost_total_ticks}` ticks · status `{view.cost_status}`",
        "",
        "Per generation:",
    ]
    for creative_id, ticks, status in view.per_generation_costs:
        lines.append(f"- `{creative_id}`: **{ticks}** ticks · `{status}`")
    lines.extend(
        [
            "",
            "Zero ticks here are the synthetic fixture's reported cost, not an absent measurement. "
            "An unreported provider cost would be unknown and would block further calls.",
        ]
    )
    return "\n".join(lines)


def _gate_rows(ladder: tuple[GateView, ...]) -> list[list[str]]:
    rows: list[list[str]] = []
    for gate in ladder:
        result = "PASS" if gate.passed else "FAIL"
        coercion = gate.coerce_to or ("" if gate.passed else "none recorded")
        if gate.passed and gate.coerce_to:
            coercion = f"coerced to {gate.coerce_to}"
        elif not gate.passed and gate.coerce_to:
            coercion = f"coerce_to {gate.coerce_to}"
        rows.append([gate.gate, gate.title, result, gate.code, coercion or "-"])
    return rows


def _decision_banner(view: ImagineSignalView) -> str:
    return (
        f"## Final action: `{view.final_action}`\n"
        f"Evidence class **{view.evidence_class}** permits this ceiling. "
        f"Proposed action was `{view.proposed_action}`. "
        "Production remains NO_GO; the action ceiling is TEST."
    )


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


__all__ = [
    "FamilyMemberView",
    "GateView",
    "ImagineSignalUIError",
    "ImagineSignalView",
    "create_imagine_signal_app",
    "load_imagine_signal_view",
    "render_imagine_signal_panel",
    "ui_mode",
]
