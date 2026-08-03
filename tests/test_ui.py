from __future__ import annotations

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


def test_ui_rejects_non_demo_mode(monkeypatch):
    from adjacency.ui import UIModeError, create_app

    monkeypatch.setenv("ADJ_UI_MODE", "live")

    with pytest.raises(UIModeError, match="only demo"):
        create_app(root=Path(__file__).resolve().parents[1], step_delay_seconds=0)
