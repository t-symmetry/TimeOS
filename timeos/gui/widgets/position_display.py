"""Position Display Widget - Current temporal position."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
)
from PySide6.QtCore import Qt

from timeos.gui.models.machine_model import MachineModel


class PositionDisplay(QGroupBox):
    """Display current temporal position."""

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("POSITION", parent)

        self._model = model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the display UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Current time (large display)
        time_layout = QHBoxLayout()
        time_label = QLabel("t =")
        time_label.setStyleSheet("color: #808080; font-size: 14pt;")
        time_layout.addWidget(time_label)

        self._time_value = QLabel("0.000")
        self._time_value.setStyleSheet(
            "color: #00ff88; font-size: 18pt; font-weight: bold; font-family: monospace;"
        )
        self._time_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_layout.addWidget(self._time_value)

        time_unit = QLabel("s")
        time_unit.setStyleSheet("color: #808080; font-size: 14pt;")
        time_layout.addWidget(time_unit)

        layout.addLayout(time_layout)

        # Reference frame
        frame_layout = QHBoxLayout()
        frame_label = QLabel("frame:")
        frame_label.setStyleSheet("color: #808080;")
        frame_layout.addWidget(frame_label)

        self._frame_value = QLabel("origin")
        self._frame_value.setStyleSheet("color: #00ff88; font-family: monospace;")
        self._frame_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        frame_layout.addWidget(self._frame_value)

        layout.addLayout(frame_layout)

        # Delta from anchor
        delta_layout = QHBoxLayout()
        delta_label = QLabel("Δt =")
        delta_label.setStyleSheet("color: #808080;")
        delta_layout.addWidget(delta_label)

        self._delta_value = QLabel("0.000")
        self._delta_value.setStyleSheet("color: #00ff88; font-family: monospace;")
        self._delta_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        delta_layout.addWidget(self._delta_value)

        delta_unit = QLabel("s")
        delta_unit.setStyleSheet("color: #808080;")
        delta_layout.addWidget(delta_unit)

        layout.addLayout(delta_layout)

        # Uncertainty
        unc_layout = QHBoxLayout()
        unc_label = QLabel("±")
        unc_label.setStyleSheet("color: #808080;")
        unc_layout.addWidget(unc_label)

        self._uncertainty_value = QLabel("0.000")
        self._uncertainty_value.setStyleSheet("color: #808080; font-family: monospace;")
        self._uncertainty_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        unc_layout.addWidget(self._uncertainty_value)

        unc_unit = QLabel("s")
        unc_unit.setStyleSheet("color: #808080;")
        unc_layout.addWidget(unc_unit)

        layout.addLayout(unc_layout)

    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.state_changed.connect(self._update_display)

    def _update_display(self) -> None:
        """Update display from model."""
        state = self._model.get_state()

        # Current time
        t = state.get("current_time", 0.0)
        self._time_value.setText(f"{t:.3f}")

        # Frame
        frame = state.get("frame", "origin")
        self._frame_value.setText(frame)

        # Delta from anchor
        anchor_t = state.get("anchor_time")
        if anchor_t is not None:
            delta = t - anchor_t
            self._delta_value.setText(f"{delta:+.3f}")
        else:
            self._delta_value.setText("---")

        # Uncertainty
        uncertainty = state.get("uncertainty", 0.0)
        self._uncertainty_value.setText(f"{uncertainty:.6f}")
