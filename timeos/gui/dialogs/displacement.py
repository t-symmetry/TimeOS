"""Displacement Dialog - Plan and execute temporal displacement."""

from __future__ import annotations

import math

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QDoubleSpinBox,
    QComboBox,
    QFrame,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt

from timeos.gui.models.machine_model import MachineModel
from timeos.physics import lorentz_factor, SPEED_OF_LIGHT


class DisplacementDialog(QDialog):
    """Dialog for planning temporal displacement."""

    def __init__(self, model: MachineModel, parent=None):
        super().__init__(parent)

        self._model = model
        self._target_time = 0.0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Plan Displacement")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Target input section
        target_group = QGroupBox("Target")
        target_layout = QVBoxLayout(target_group)

        # Time input
        time_layout = QHBoxLayout()
        time_label = QLabel("Target Time:")
        time_label.setStyleSheet("color: #808080;")
        time_layout.addWidget(time_label)

        self._time_input = QDoubleSpinBox()
        self._time_input.setRange(-1e15, 1e15)
        self._time_input.setValue(0.0)
        self._time_input.setDecimals(3)
        self._time_input.setSuffix(" s")
        self._time_input.setMinimumWidth(150)
        time_layout.addWidget(self._time_input)

        target_layout.addLayout(time_layout)

        # Frame selection
        frame_layout = QHBoxLayout()
        frame_label = QLabel("Reference Frame:")
        frame_label.setStyleSheet("color: #808080;")
        frame_layout.addWidget(frame_label)

        self._frame_combo = QComboBox()
        self._frame_combo.addItems(["origin", "anchor", "current"])
        frame_layout.addWidget(self._frame_combo)

        target_layout.addLayout(frame_layout)

        layout.addWidget(target_group)

        # Calculated path section
        path_group = QGroupBox("Calculated Path")
        path_layout = QVBoxLayout(path_group)

        # Path type
        self._path_type = self._create_info_row("Type:", "DIRECT")
        path_layout.addLayout(self._path_type)

        # Risk level
        self._risk_level = self._create_info_row("Risk:", "LOW")
        path_layout.addLayout(self._risk_level)

        # Energy required
        self._energy_required = self._create_info_row("Energy:", "0.00e+00 J")
        path_layout.addLayout(self._energy_required)

        # Relativistic velocity (beta)
        self._beta_row = self._create_info_row("β (v/c):", "0.0000")
        path_layout.addLayout(self._beta_row)

        # Lorentz factor (gamma)
        self._gamma_row = self._create_info_row("γ:", "1.0000")
        path_layout.addLayout(self._gamma_row)

        # Proper time for traveler
        self._proper_time = self._create_info_row("Proper Time:", "0.00 s")
        path_layout.addLayout(self._proper_time)

        # Paradox probability
        self._paradox_prob = self._create_info_row("Paradox Prob:", "0.0%")
        path_layout.addLayout(self._paradox_prob)

        # Duration
        self._duration = self._create_info_row("Duration:", "0.00 s")
        path_layout.addLayout(self._duration)

        layout.addWidget(path_group)

        # Warnings section (initially hidden)
        self._warnings_group = QGroupBox("Warnings")
        self._warnings_group.setStyleSheet("QGroupBox { color: #ffaa00; }")
        warnings_layout = QVBoxLayout(self._warnings_group)

        self._warnings_label = QLabel()
        self._warnings_label.setStyleSheet("color: #ffaa00;")
        self._warnings_label.setWordWrap(True)
        warnings_layout.addWidget(self._warnings_label)

        self._warnings_group.setVisible(False)
        layout.addWidget(self._warnings_group)

        # Buttons
        button_layout = QHBoxLayout()

        self._execute_btn = QPushButton("EXECUTE")
        self._execute_btn.setProperty("primary", True)
        self._execute_btn.setMinimumSize(100, 36)
        button_layout.addWidget(self._execute_btn)

        self._cancel_btn = QPushButton("CANCEL")
        self._cancel_btn.setMinimumSize(100, 36)
        button_layout.addWidget(self._cancel_btn)

        layout.addLayout(button_layout)

    def _create_info_row(self, label: str, value: str) -> QHBoxLayout:
        """Create an info row with label and value."""
        layout = QHBoxLayout()

        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #808080;")
        label_widget.setMinimumWidth(100)
        layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("color: #00ff88; font-family: monospace;")
        value_widget.setObjectName(f"value_{label.replace(':', '')}")
        layout.addWidget(value_widget)

        layout.addStretch()

        return layout

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._time_input.valueChanged.connect(self._on_target_changed)
        self._frame_combo.currentIndexChanged.connect(self._on_target_changed)
        self._execute_btn.clicked.connect(self.accept)
        self._cancel_btn.clicked.connect(self.reject)

    def _on_target_changed(self) -> None:
        """Handle target change - recalculate path with relativistic physics."""
        target_time = self._time_input.value()
        frame = self._frame_combo.currentText()

        # Get current state
        state = self._model.get_state()
        current_time = state.get("current_time", 0.0)

        # Calculate displacement
        delta_t = target_time - current_time

        # Relativistic calculations
        # Assume displacement requires accelerating to some fraction of c
        # Higher displacements require higher velocities
        # Model: v = c * tanh(|Δt| / t_scale) where t_scale controls velocity scaling
        t_scale = 1e6  # Time scale for velocity saturation
        beta = math.tanh(abs(delta_t) / t_scale)  # v/c approaches 1 asymptotically

        # Calculate Lorentz factor
        if beta < 0.9999:
            gamma = lorentz_factor(beta)
        else:
            gamma = 100.0  # Cap at very high gamma for display

        # Proper time experienced by traveler: τ = t / γ
        coord_duration = abs(delta_t) * 0.001  # Duration in coordinate time
        proper_time_val = coord_duration / gamma if gamma > 0 else coord_duration

        # Relativistic energy: E = γmc²
        # Using effective mass of 1kg for the "temporal payload"
        rest_mass = 1.0  # kg (effective temporal payload mass)
        rest_energy = rest_mass * SPEED_OF_LIGHT ** 2  # E₀ = mc²
        total_energy = gamma * rest_energy  # E = γmc²
        kinetic_energy = (gamma - 1) * rest_energy  # K = (γ-1)mc²

        # Use kinetic energy for display (energy needed beyond rest mass)
        energy = kinetic_energy if beta > 0 else abs(delta_t) * 1e6

        # Estimate risk based on gamma (high relativistic factor = higher risk)
        if gamma < 1.01:
            risk = "MINIMAL"
            risk_color = "#00ff88"
        elif gamma < 1.25:
            risk = "LOW"
            risk_color = "#00ff88"
        elif gamma < 2.0:
            risk = "MODERATE"
            risk_color = "#ffaa00"
        elif gamma < 10.0:
            risk = "HIGH"
            risk_color = "#ff4444"
        else:
            risk = "EXTREME"
            risk_color = "#ff0000"

        # Estimate paradox probability (higher at extreme relativistic speeds)
        paradox_prob = min(50.0, (gamma - 1) * 5.0)

        # Update display
        self._update_value("Type", "DIRECT" if beta < 0.5 else ("PHASED" if beta < 0.9 else "EXTREME"))

        risk_label = self._find_value_label("Risk")
        if risk_label:
            risk_label.setText(risk)
            risk_label.setStyleSheet(f"color: {risk_color}; font-family: monospace;")

        self._update_value("Energy", f"{energy:.2e} J")
        self._update_value("β(v/c)", f"{beta:.4f}")
        self._update_value("γ", f"{gamma:.4f}")
        self._update_value("ProperTime", f"{proper_time_val:.4f} s")
        self._update_value("ParadoxProb", f"{paradox_prob:.1f}%")
        self._update_value("Duration", f"{coord_duration:.4f} s")

        # Show warnings if needed
        warnings = []
        if gamma > 2.0:
            warnings.append(f"Relativistic regime: γ={gamma:.2f} causes significant time dilation")
        if beta > 0.9:
            warnings.append(f"Near-lightspeed velocity: β={beta:.3f}c")
        if abs(delta_t) > 1e9:
            warnings.append("Large displacement may cause timeline instability")
        if paradox_prob > 5:
            warnings.append("Elevated paradox risk - review causality constraints")
        if energy > 1e15:
            warnings.append("Energy exceeds standard reserves")
        if proper_time_val < coord_duration * 0.5:
            warnings.append(f"Traveler will age {(coord_duration - proper_time_val):.2f}s less than coordinate time")

        if warnings:
            self._warnings_group.setVisible(True)
            self._warnings_label.setText("\n".join(f"• {w}" for w in warnings))
        else:
            self._warnings_group.setVisible(False)

        self._target_time = target_time

    def _update_value(self, label: str, value: str) -> None:
        """Update a value label."""
        label_widget = self._find_value_label(label)
        if label_widget:
            label_widget.setText(value)

    def _find_value_label(self, label: str) -> QLabel | None:
        """Find a value label by its associated label text."""
        name = f"value_{label.replace(':', '').replace(' ', '')}"
        return self.findChild(QLabel, name)

    def get_target(self) -> float:
        """Get the selected target time.

        Returns:
            Target time in seconds.
        """
        return self._target_time
