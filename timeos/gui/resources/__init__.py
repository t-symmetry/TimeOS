"""TimeOS GUI Resources.

Stylesheets, icons, and other assets.
"""

from pathlib import Path


def load_stylesheet() -> str:
    """Load the main application stylesheet.

    Returns:
        CSS/QSS stylesheet string.
    """
    style_path = Path(__file__).parent / "style.qss"
    if style_path.exists():
        return style_path.read_text()
    return ""


__all__ = ["load_stylesheet"]
