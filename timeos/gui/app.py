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

    If no mode flags are set, shows a mode selector dialog.

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
    app.setOrganizationName("Skylark Software LLC")

    # Set default font
    font = QFont("Monospace", 10)
    font.setStyleHint(QFont.StyleHint.Monospace)
    app.setFont(font)

    # Load stylesheet
    stylesheet = load_stylesheet()
    app.setStyleSheet(stylesheet)

    # If no mode specified, show mode selector
    if not any([demo, emulated, ros2]):
        from timeos.gui.dialogs.mode_selector import ModeSelector

        selector = ModeSelector()
        if selector.exec() != ModeSelector.DialogCode.Accepted:
            return 0  # User cancelled

        demo, emulated, ros2 = selector.get_mode()

    # Create and show main window
    window = MainWindow(demo=demo, emulated=emulated, ros2=ros2)
    window.show()

    return app.exec()
