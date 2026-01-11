"""Mode Selector Dialog - Choose operating mode on startup."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QCheckBox,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ModeSelector(QDialog):
    """Dialog for selecting TimeOS operating mode."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("TimeOS")
        self.setFixedSize(400, 320)
        self.setModal(True)

        self._mode = "demo"  # Default
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Title
        title = QLabel("TimeOS Control")
        title.setFont(QFont("", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Select operating mode")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888;")
        layout.addWidget(subtitle)

        # Mode selection
        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._button_group = QButtonGroup(self)

        modes = [
            ("demo", "Demo", "Simulated activity for demonstrations"),
            ("emulated", "Emulated", "Realistic hardware emulation with thermal modeling"),
            ("normal", "Normal", "Direct hardware abstraction (no simulation)"),
            ("ros2", "ROS2", "Connect to ROS2 nodes for hardware control"),
        ]

        for i, (mode_id, name, description) in enumerate(modes):
            radio = QRadioButton(name)
            radio.setProperty("mode_id", mode_id)
            if mode_id == "demo":
                radio.setChecked(True)

            # Add description as tooltip
            radio.setToolTip(description)

            self._button_group.addButton(radio, i)
            mode_layout.addWidget(radio)

            # Description label
            desc = QLabel(f"  {description}")
            desc.setStyleSheet("color: #666; font-size: 10px; margin-left: 20px;")
            mode_layout.addWidget(desc)

        layout.addWidget(mode_group)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #333;")
        layout.addWidget(line)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.reject)
        button_layout.addWidget(quit_btn)

        start_btn = QPushButton("Start")
        start_btn.setDefault(True)
        start_btn.clicked.connect(self._on_start)
        start_btn.setStyleSheet("font-weight: bold;")
        button_layout.addWidget(start_btn)

        layout.addLayout(button_layout)

    def _on_start(self) -> None:
        """Handle start button click."""
        checked = self._button_group.checkedButton()
        if checked:
            self._mode = checked.property("mode_id")
        self.accept()

    def get_mode(self) -> tuple[bool, bool, bool]:
        """Get selected mode as (demo, emulated, ros2) flags."""
        return (
            self._mode == "demo",
            self._mode == "emulated",
            self._mode == "ros2",
        )

    def get_mode_name(self) -> str:
        """Get mode name string."""
        return self._mode
