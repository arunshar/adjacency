from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

gr = pytest.importorskip("gradio")

pytestmark = pytest.mark.integration


def test_ui_builds_in_demo_mode_even_when_an_api_key_is_present(monkeypatch):
    from adjacency.autopsy import load_autopsy_bundle, render_evidence_image
    from adjacency.ui import create_app

    root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("ADJ_UI_MODE", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "present-but-unused")

    app = create_app(root=root, step_delay_seconds=0)
    config = app.get_config_file()
    labels = {component.get("props", {}).get("label") for component in config["components"]}
    bundle = load_autopsy_bundle(root)
    wow = bundle.record(bundle.wow_item_id)
    rendered = render_evidence_image(wow)

    assert isinstance(app, gr.Blocks)
    assert "Agreement traces" in labels
    assert "Structured trace and full gate chain" in labels
    assert rendered is not None
    assert rendered.getpixel((200, 20)) == (220, 38, 38)


def test_autopsy_css_branches_theme_colors_and_targets_gate_heading():
    from adjacency.ui import AUTOPSY_CSS

    assert "--adj-mode-badge-background: #ecfdf5" in AUTOPSY_CSS
    assert "--adj-gate-banner-background: #fff1f2" in AUTOPSY_CSS
    assert "body.dark .gradio-container" in AUTOPSY_CSS
    assert "--adj-mode-badge-background: #12372a" in AUTOPSY_CSS
    assert "--adj-gate-banner-text: #fecaca" in AUTOPSY_CSS
    assert "color: var(--adj-mode-badge-text) !important" in AUTOPSY_CSS
    assert "background: var(--adj-gate-banner-background) !important" in AUTOPSY_CSS
    assert ".gate-banner h2" in AUTOPSY_CSS
    assert "color: var(--adj-gate-banner-text) !important" in AUTOPSY_CSS


def test_ui_rejects_non_demo_mode(monkeypatch):
    from adjacency.ui import UIModeError, create_app

    monkeypatch.setenv("ADJ_UI_MODE", "live")

    with pytest.raises(UIModeError, match="only demo"):
        create_app(root=Path(__file__).resolve().parents[1], step_delay_seconds=0)


def test_demo_path_never_imports_or_connects_to_temporal():
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(
        {
            "ADJ_HITL_BACKEND": "temporal",
            "TEMPORAL_ADDRESS": "unreachable.invalid:7233",
            "TEMPORAL_NAMESPACE": "unreachable",
            "TEMPORAL_API_KEY": "unused",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import sys",
                    "from adjacency.ui import create_app",
                    f"create_app(root={str(root)!r}, step_delay_seconds=0)",
                    "assert 'temporalio' not in sys.modules",
                )
            ),
        ],
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
