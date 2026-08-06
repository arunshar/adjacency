"""Read-only ImagineSignal Gradio surface tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

gr = pytest.importorskip("gradio")

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_imagine_signal_view_from_frozen_artifact():
    from adjacency.imagine_signal.ui import load_imagine_signal_view

    view = load_imagine_signal_view(REPO_ROOT)

    assert len(view.family) == 3
    assert view.changed_axis == "background_tone"
    assert view.locked_attributes == ("composition", "logo", "product_identity", "text")
    assert view.final_action == "TEST"
    assert view.evidence_class == "FROZEN_REPLAY"
    assert view.cost_status == "EXACT"
    assert view.network_used is False
    assert view.provider_call_used is False
    assert len(view.gate_ladder) == 9
    assert [gate.gate for gate in view.gate_ladder] == [
        "IS0",
        "IS1",
        "IS2",
        "IS3",
        "IS4",
        "IS5",
        "IS6",
        "IS7",
        "IS8",
    ]
    assert all(gate.passed for gate in view.gate_ladder)
    assert all(member.image_path.is_file() for member in view.family)
    assert "not measured provider efficiency" in view.efficiency_note


def test_imagine_signal_app_builds_read_only_labels(monkeypatch):
    from adjacency.imagine_signal.ui import create_imagine_signal_app

    monkeypatch.delenv("ADJ_UI_MODE", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "present-but-unused")

    app = create_imagine_signal_app(root=REPO_ROOT)
    config = app.get_config_file()
    labels = {component.get("props", {}).get("label") for component in config["components"]}
    text_values = [
        str(component.get("props", {}).get("value") or "") for component in config["components"]
    ]
    joined = "\n".join(text_values)

    assert isinstance(app, gr.Blocks)
    assert "ImagineSignal gates" in labels
    assert "Frozen decision slice" in labels
    assert "demo-control" in labels
    assert "background_tone" in joined
    assert "FROZEN_REPLAY" in joined
    assert "composition" in joined
    assert "READ ONLY" in joined


def test_combined_app_exposes_both_surfaces(monkeypatch):
    import importlib.util

    monkeypatch.delenv("ADJ_UI_MODE", raising=False)
    app_path = REPO_ROOT / "app.py"
    spec = importlib.util.spec_from_file_location("adjacency_demo_app", app_path)
    assert spec is not None and spec.loader is not None
    demo_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo_app)
    combined = demo_app.create_combined_app(root=REPO_ROOT, step_delay_seconds=0)
    config = combined.get_config_file()
    labels = {component.get("props", {}).get("label") for component in config["components"]}

    assert "Agreement traces" in labels
    assert "ImagineSignal gates" in labels
    assert "Structured trace and full gate chain" in labels


def test_imagine_signal_ui_rejects_non_demo_mode(monkeypatch):
    from adjacency.imagine_signal.ui import ImagineSignalUIError, load_imagine_signal_view

    monkeypatch.setenv("ADJ_UI_MODE", "live")
    with pytest.raises(ImagineSignalUIError, match="only demo"):
        load_imagine_signal_view(REPO_ROOT)


def test_imagine_signal_path_never_imports_xai_live_or_opens_network():
    environment = os.environ.copy()
    environment.pop("XAI_API_KEY", None)
    environment.pop("ADJ_RECORD", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                (
                    "import sys",
                    "from adjacency.imagine_signal.ui import "
                    "load_imagine_signal_view, create_imagine_signal_app",
                    f"view = load_imagine_signal_view({str(REPO_ROOT)!r})",
                    "assert view.network_used is False",
                    "assert view.provider_call_used is False",
                    f"create_imagine_signal_app(root={str(REPO_ROOT)!r})",
                    "assert 'adjacency.imagine_signal.adapters.xai_live' not in sys.modules",
                )
            ),
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
