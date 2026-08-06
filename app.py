"""Launch the bundled Adjacency demo surfaces."""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from adjacency.imagine_signal.ui import load_imagine_signal_view, render_imagine_signal_panel
from adjacency.ui import AUTOPSY_CSS, AUTOPSY_THEME, render_autopsy_panel, ui_mode

REPO_ROOT = Path(__file__).resolve().parent


def create_combined_app(
    *,
    root: Path | str | None = None,
    step_delay_seconds: float = 0.06,
) -> gr.Blocks:
    """Build Autopsy and ImagineSignal as tabs over the same frozen demo theme."""

    ui_mode()
    repo_root = Path(root).resolve() if root is not None else REPO_ROOT
    imagine_view = load_imagine_signal_view(repo_root)

    with gr.Blocks(fill_width=True, title="Adjacency") as app:
        with gr.Tabs():
            with gr.Tab("ImagineSignal"):
                render_imagine_signal_panel(imagine_view)
            with gr.Tab("Autopsy"):
                render_autopsy_panel(root=repo_root, step_delay_seconds=step_delay_seconds)

    return app.queue(default_concurrency_limit=2)


demo = create_combined_app()

if __name__ == "__main__":
    demo.launch(css=AUTOPSY_CSS, theme=AUTOPSY_THEME, show_error=True)
