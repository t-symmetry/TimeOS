"""Position Display Widget - Current temporal position with relativistic quantities."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QFrame,
)
from PySide6.QtCore import Qt

from timeos.gui.models.machine_model import MachineModel
from timeos.physics import lorentz_factor


class PositionDisplay(QGroupBox):
    """Display current temporal position with relativistic physics."""

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("POSITION", parent)

        self._model = model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the display UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

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

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep)

        # Relativistic quantities section
        rel_label = QLabel("RELATIVISTIC")
        rel_label.setStyleSheet("color: #5a5a5a; font-size: 8pt;")
        layout.addWidget(rel_label)

        # Lorentz factor (gamma)
        gamma_layout = QHBoxLayout()
        gamma_label = QLabel("γ =")
        gamma_label.setStyleSheet("color: #808080;")
        gamma_label.setToolTip("Lorentz factor: γ = 1/√(1-v²/c²)")
        gamma_layout.addWidget(gamma_label)

        self._gamma_value = QLabel("1.000")
        self._gamma_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._gamma_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._gamma_value.setToolTip("Time dilation factor")
        gamma_layout.addWidget(self._gamma_value)

        layout.addLayout(gamma_layout)

        # Proper time (tau)
        tau_layout = QHBoxLayout()
        tau_label = QLabel("τ =")
        tau_label.setStyleSheet("color: #808080;")
        tau_label.setToolTip("Proper time: time experienced by traveler")
        tau_layout.addWidget(tau_label)

        self._tau_value = QLabel("0.000")
        self._tau_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._tau_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._tau_value.setToolTip("Proper time (traveler's clock)")
        tau_layout.addWidget(self._tau_value)

        tau_unit = QLabel("s")
        tau_unit.setStyleSheet("color: #808080;")
        tau_layout.addWidget(tau_unit)

        layout.addLayout(tau_layout)

        # Velocity as fraction of c
        beta_layout = QHBoxLayout()
        beta_label = QLabel("β =")
        beta_label.setStyleSheet("color: #808080;")
        beta_label.setToolTip("Velocity as fraction of c: β = v/c")
        beta_layout.addWidget(beta_label)

        self._beta_value = QLabel("0.000")
        self._beta_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._beta_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._beta_value.setToolTip("v/c (fraction of light speed)")
        beta_layout.addWidget(self._beta_value)

        beta_unit = QLabel("c")
        beta_unit.setStyleSheet("color: #808080;")
        beta_layout.addWidget(beta_unit)

        layout.addLayout(beta_layout)

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

        # Relativistic quantities
        beta = state.get("velocity_beta", 0.0)
        gamma = state.get("lorentz_gamma", 1.0)
        proper_time = state.get("proper_time", t)

        # Calculate gamma from beta if not provided
        if gamma == 1.0 and beta > 0:
            try:
                gamma = lorentz_factor(beta)
            except ValueError:
                gamma = 1.0

        self._gamma_value.setText(f"{gamma:.4f}")
        self._beta_value.setText(f"{beta:.4f}")
        self._tau_value.setText(f"{proper_time:.3f}")
