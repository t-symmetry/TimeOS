"""Control Panel Widget - Operation controls."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QLineEdit,
    QDoubleSpinBox,
)
from PySide6.QtCore import Qt, Signal

from timeos.gui.models.machine_model import MachineModel


class ControlPanel(QGroupBox):
    """Control panel with operation buttons."""

    # Signals
    displace_requested = Signal()
    return_requested = Signal()
    estop_requested = Signal()

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("CONTROLS", parent)

        self._model = model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the control panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)

        # Displace button
        self._displace_btn = QPushButton("DISPLACE")
        self._displace_btn.setProperty("primary", True)
        self._displace_btn.setMinimumSize(100, 40)
        self._displace_btn.setToolTip("Open displacement planning dialog")
        button_layout.addWidget(self._displace_btn)

        # Return button
        self._return_btn = QPushButton("RETURN")
        self._return_btn.setMinimumSize(100, 40)
        self._return_btn.setToolTip("Return to anchor point")
        button_layout.addWidget(self._return_btn)

        # Spacer
        button_layout.addStretch()

        # E-Stop button
        self._estop_btn = QPushButton("E-STOP")
        self._estop_btn.setProperty("danger", True)
        self._estop_btn.setMinimumSize(100, 40)
        self._estop_btn.setToolTip("Emergency stop all operations")
        button_layout.addWidget(self._estop_btn)

        layout.addLayout(button_layout)

        # Input row
        input_layout = QHBoxLayout()
        input_layout.setSpacing(24)

        # Quick target input
        target_layout = QHBoxLayout()
        target_label = QLabel("Target:")
        target_label.setStyleSheet("color: #808080;")
        target_layout.addWidget(target_label)

        self._target_input = QDoubleSpinBox()
        self._target_input.setRange(-1e10, 1e10)
        self._target_input.setValue(0.0)
        self._target_input.setDecimals(3)
        self._target_input.setSuffix(" s")
        self._target_input.setMinimumWidth(120)
        target_layout.addWidget(self._target_input)

        input_layout.addLayout(target_layout)

        # Energy display
        energy_layout = QHBoxLayout()
        energy_label = QLabel("Energy budget:")
        energy_label.setStyleSheet("color: #808080;")
        energy_layout.addWidget(energy_label)

        self._energy_display = QLabel("1.00e+15 J")
        self._energy_display.setStyleSheet("color: #00ff88; font-family: monospace;")
        energy_layout.addWidget(self._energy_display)

        input_layout.addLayout(energy_layout)

        input_layout.addStretch()

        layout.addLayout(input_layout)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._displace_btn.clicked.connect(self._on_displace)
        self._return_btn.clicked.connect(self._on_return)
        self._estop_btn.clicked.connect(self._on_estop)

        self._model.state_changed.connect(self._update_state)

    def _on_displace(self) -> None:
        """Handle displace button click."""
        self.displace_requested.emit()

    def _on_return(self) -> None:
        """Handle return button click."""
        self.return_requested.emit()

    def _on_estop(self) -> None:
        """Handle E-Stop button click."""
        self.estop_requested.emit()

    def _update_state(self) -> None:
        """Update UI based on model state."""
        state = self._model.get_state()

        # Enable/disable buttons based on state
        initialized = state.get("initialized", False)
        is_displacing = state.get("is_displacing", False)
        anchor_connected = state.get("anchor_connected", False)

        self._displace_btn.setEnabled(initialized and not is_displacing)
        self._return_btn.setEnabled(initialized and anchor_connected and not is_displacing)
        # E-Stop is always enabled

    def get_target_time(self) -> float:
        """Get the target time from the input.

        Returns:
            Target time in seconds.
        """
        return self._target_input.value()
