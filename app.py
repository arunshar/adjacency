"""Launch the bundled Adjacency Autopsy demo."""

from adjacency.ui import AUTOPSY_CSS, AUTOPSY_THEME, create_app

demo = create_app()

if __name__ == "__main__":
    demo.launch(css=AUTOPSY_CSS, theme=AUTOPSY_THEME, show_error=True)
