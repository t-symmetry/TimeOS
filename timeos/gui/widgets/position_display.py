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
        time_label.setToolTip(
            "<b>Coordinate Time (t)</b><br><br>"
            "Time measured in the current reference frame.<br><br>"
            "This is the 'wall clock' time in the lab/origin frame,<br>"
            "not the traveler's personal (proper) time.<br><br>"
            "Different observers may disagree about coordinate time<br>"
            "due to relativity of simultaneity."
        )
        time_layout.addWidget(time_label)

        self._time_value = QLabel("0.000")
        self._time_value.setStyleSheet(
            "color: #00ff88; font-size: 18pt; font-weight: bold; font-family: monospace;"
        )
        self._time_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._time_value.setToolTip(
            "<b>Current Coordinate Time</b><br><br>"
            "The time coordinate in the reference frame."
        )
        time_layout.addWidget(self._time_value)

        time_unit = QLabel("s")
        time_unit.setStyleSheet("color: #808080; font-size: 14pt;")
        time_layout.addWidget(time_unit)

        layout.addLayout(time_layout)

        # Reference frame
        frame_layout = QHBoxLayout()
        frame_label = QLabel("frame:")
        frame_label.setStyleSheet("color: #808080;")
        frame_label.setToolTip(
            "<b>Reference Frame</b><br><br>"
            "The coordinate system in which measurements are made.<br><br>"
            "In special relativity, different frames may measure<br>"
            "different times and distances for the same events.<br><br>"
            "Common frames:<br>"
            "• <b>origin</b>: The lab/base frame<br>"
            "• <b>ship</b>: A moving observer's frame<br>"
            "• <b>earth_tai</b>: Earth's atomic time standard"
        )
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
        delta_label.setToolTip(
            "<b>Time Displacement (Δt)</b><br><br>"
            "Time difference from the anchor point.<br><br>"
            "Positive: future relative to anchor<br>"
            "Negative: past relative to anchor<br><br>"
            "The anchor is your 'home' time - the point you can<br>"
            "safely return to."
        )
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
        unc_label.setToolTip(
            "<b>Time Uncertainty</b><br><br>"
            "Measurement uncertainty in the time coordinate.<br><br>"
            "Sources of uncertainty include:<br>"
            "• Clock precision and drift<br>"
            "• Synchronization errors<br>"
            "• Quantum effects (at small scales)<br>"
            "• Gravitational time dilation gradients<br><br>"
            "Lower values indicate more precise positioning."
        )
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
        gamma_label.setToolTip(
            "<b>Lorentz Factor (γ)</b><br><br>"
            "γ = 1/√(1 - v²/c²)<br><br>"
            "The Lorentz factor determines how much time dilates "
            "and length contracts at relativistic speeds.<br><br>"
            "<b>Examples:</b><br>"
            "• γ = 1.0 at rest<br>"
            "• γ = 1.15 at 0.5c (half light speed)<br>"
            "• γ = 2.29 at 0.9c<br>"
            "• γ = 7.09 at 0.99c<br><br>"
            "As v → c, γ → ∞"
        )
        gamma_layout.addWidget(gamma_label)

        self._gamma_value = QLabel("1.000")
        self._gamma_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._gamma_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._gamma_value.setToolTip(
            "<b>Current Time Dilation Factor</b><br><br>"
            "For every second that passes on the traveler's clock,<br>"
            "γ seconds pass in the stationary frame.<br><br>"
            "γ = 1.0 means no time dilation (at rest)."
        )
        gamma_layout.addWidget(self._gamma_value)

        layout.addLayout(gamma_layout)

        # Proper time (tau)
        tau_layout = QHBoxLayout()
        tau_label = QLabel("τ =")
        tau_label.setStyleSheet("color: #808080;")
        tau_label.setToolTip(
            "<b>Proper Time (τ)</b><br><br>"
            "The time measured by a clock traveling with the observer.<br><br>"
            "Proper time is <i>invariant</i> - all observers agree on it.<br>"
            "It's the 'personal' time experienced by the traveler.<br><br>"
            "<b>Relation to coordinate time:</b><br>"
            "dτ = dt/γ<br><br>"
            "A moving clock runs slow by factor γ compared to<br>"
            "stationary clocks (time dilation)."
        )
        tau_layout.addWidget(tau_label)

        self._tau_value = QLabel("0.000")
        self._tau_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._tau_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._tau_value.setToolTip(
            "<b>Accumulated Proper Time</b><br><br>"
            "Total time experienced by the traveler<br>"
            "since the origin.<br><br>"
            "Less than coordinate time t when moving."
        )
        tau_layout.addWidget(self._tau_value)

        tau_unit = QLabel("s")
        tau_unit.setStyleSheet("color: #808080;")
        tau_layout.addWidget(tau_unit)

        layout.addLayout(tau_layout)

        # Velocity as fraction of c
        beta_layout = QHBoxLayout()
        beta_label = QLabel("β =")
        beta_label.setStyleSheet("color: #808080;")
        beta_label.setToolTip(
            "<b>Velocity Parameter (β)</b><br><br>"
            "β = v/c<br><br>"
            "Velocity expressed as a fraction of the speed of light.<br><br>"
            "<b>Physical meaning:</b><br>"
            "• β = 0: at rest<br>"
            "• β = 0.1: 10% of light speed (~30,000 km/s)<br>"
            "• β = 0.5: half light speed (~150,000 km/s)<br>"
            "• β = 1: light speed (impossible for massive objects)<br><br>"
            "c = 299,792,458 m/s ≈ 3×10⁸ m/s"
        )
        beta_layout.addWidget(beta_label)

        self._beta_value = QLabel("0.000")
        self._beta_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._beta_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._beta_value.setToolTip(
            "<b>Current Velocity (v/c)</b><br><br>"
            "Current speed as fraction of light speed.<br><br>"
            "β = 0 means at rest relative to anchor frame."
        )
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
