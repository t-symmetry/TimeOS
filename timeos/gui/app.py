"""TimeOS GUI Application launcher."""

from __future__ import annotations

import sys
from pathlib import Path


def launch(demo: bool = False, emulated: bool = False, ros2: bool = False) -> int:
    """Launch the TimeOS GUI application.

    Args:
        demo: If True, launch with demo data.
        emulated: If True, use emulated hardware modules.
        ros2: If True, use ROS2 for all hardware communication.

    Returns:
        Exit code.
    """
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
    except ImportError:
        print("Error: PySide6 is required for the GUI.")
        print("Install with: pip install timeos[gui]")
        return 1

    from timeos.gui.main import MainWindow
    from timeos.gui.resources import load_stylesheet

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("TimeOS Control")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("T-Symmetry Labs")

    # Set default font
    font = QFont("Monospace", 10)
    font.setStyleHint(QFont.StyleHint.Monospace)
    app.setFont(font)

    # Load stylesheet
    stylesheet = load_stylesheet()
    app.setStyleSheet(stylesheet)

    # Create and show main window
    window = MainWindow(demo=demo, emulated=emulated, ros2=ros2)
    window.show()

    return app.exec()
