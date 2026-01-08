"""Displacement Dialog - Plan and execute temporal displacement."""

from __future__ import annotations

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
        """Handle target change - recalculate path."""
        target_time = self._time_input.value()
        frame = self._frame_combo.currentText()

        # Get current state
        state = self._model.get_state()
        current_time = state.get("current_time", 0.0)

        # Calculate displacement
        delta_t = target_time - current_time

        # Estimate energy (simplified formula)
        energy = abs(delta_t) * 1e9  # 1 GJ per second

        # Estimate risk based on delta
        if abs(delta_t) < 1:
            risk = "MINIMAL"
            risk_color = "#00ff88"
        elif abs(delta_t) < 100:
            risk = "LOW"
            risk_color = "#00ff88"
        elif abs(delta_t) < 10000:
            risk = "MODERATE"
            risk_color = "#ffaa00"
        else:
            risk = "HIGH"
            risk_color = "#ff4444"

        # Estimate paradox probability
        paradox_prob = min(0.1, abs(delta_t) / 1e8) * 100

        # Update display
        self._update_value("Type", "DIRECT" if abs(delta_t) < 1e6 else "PHASED")

        risk_label = self._find_value_label("Risk")
        if risk_label:
            risk_label.setText(risk)
            risk_label.setStyleSheet(f"color: {risk_color}; font-family: monospace;")

        self._update_value("Energy", f"{energy:.2e} J")
        self._update_value("Paradox Prob", f"{paradox_prob:.1f}%")
        self._update_value("Duration", f"{abs(delta_t) * 0.001:.2f} s")

        # Show warnings if needed
        warnings = []
        if abs(delta_t) > 1e9:
            warnings.append("Large displacement may cause timeline instability")
        if paradox_prob > 1:
            warnings.append("Elevated paradox risk - review causality constraints")
        if energy > 1e15:
            warnings.append("Energy exceeds standard reserves")

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
