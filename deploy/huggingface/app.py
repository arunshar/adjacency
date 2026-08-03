"""Launch the staged offline Adjacency Autopsy on Hugging Face Spaces."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from adjacency.ui import AUTOPSY_CSS, AUTOPSY_THEME, create_app  # noqa: E402

demo = create_app()

if __name__ == "__main__":
    demo.launch(css=AUTOPSY_CSS, theme=AUTOPSY_THEME, show_error=True)
