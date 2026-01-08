"""Status Panel Widget - Module status indicators."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer

from timeos.gui.models.machine_model import MachineModel


class StatusLED(QWidget):
    """LED-style status indicator."""

    COLORS = {
        "READY": "#00ff88",
        "ACTIVE": "#00ff88",
        "IDLE": "#00ff88",
        "NOMINAL": "#00ff88",
        "CALIBRATING": "#ffff00",
        "WARNING": "#ffaa00",
        "INITIALIZING": "#00aaff",
        "ERROR": "#ff4444",
        "FAULT": "#ff4444",
        "OFFLINE": "#5a5a5a",
        "UNKNOWN": "#5a5a5a",
    }

    def __init__(self, label: str, tooltip: str = "", parent: QWidget | None = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # LED indicator
        self._led = QLabel()
        self._led.setFixedSize(12, 12)
        self._led.setStyleSheet(self._led_style("#5a5a5a"))
        layout.addWidget(self._led)

        # Label
        self._label = QLabel(label)
        self._label.setStyleSheet("color: #e0e0e0;")
        if tooltip:
            self._label.setToolTip(tooltip)
        layout.addWidget(self._label)

        # Status text
        self._status = QLabel("OFFLINE")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._status.setStyleSheet("color: #5a5a5a; font-family: monospace;")
        layout.addWidget(self._status)

    def set_status(self, status: str) -> None:
        """Set the status and update display."""
        status_upper = status.upper()
        color = self.COLORS.get(status_upper, "#5a5a5a")

        self._led.setStyleSheet(self._led_style(color))
        self._status.setText(status_upper)
        self._status.setStyleSheet(f"color: {color}; font-family: monospace;")

    def _led_style(self, color: str) -> str:
        """Generate LED stylesheet."""
        return f"""
            background-color: {color};
            border-radius: 6px;
            border: 1px solid {color};
        """


class StatusPanel(QGroupBox):
    """System status panel showing module statuses."""

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("SYSTEM STATUS", parent)

        self._model = model
        self._leds: dict[str, StatusLED] = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # Module definitions with tooltips
        modules = {
            "TDU": (
                "<b>Temporal Displacement Unit</b><br><br>"
                "The core component responsible for temporal displacement.<br><br>"
                "Controls the spacetime manipulation field that enables<br>"
                "movement through time.<br><br>"
                "<b>Status meanings:</b><br>"
                "• READY: System nominal, ready to displace<br>"
                "• ACTIVE: Displacement in progress<br>"
                "• CALIBRATING: Adjusting field parameters<br>"
                "• ERROR: Displacement fault detected"
            ),
            "Field": (
                "<b>Field Generator</b><br><br>"
                "Generates the electromagnetic field required for<br>"
                "T-symmetry manipulation.<br><br>"
                "The field creates a localized region where the<br>"
                "arrow of time can be controlled.<br><br>"
                "<b>Key parameters:</b><br>"
                "• Field strength (Tesla)<br>"
                "• T-symmetry factor<br>"
                "• Power consumption (Watts)"
            ),
            "Causality": (
                "<b>Causality Monitor</b><br><br>"
                "Monitors timeline consistency and detects paradoxes.<br><br>"
                "Enforces causal constraints:<br>"
                "• No self-causation (causal loops)<br>"
                "• Effects cannot precede causes<br>"
                "• Relativistic causality (light cone)<br><br>"
                "<b>Status meanings:</b><br>"
                "• NOMINAL: All constraints satisfied<br>"
                "• WARNING: Elevated paradox risk<br>"
                "• ERROR: Causality violation detected"
            ),
            "Anchor": (
                "<b>Temporal Anchor</b><br><br>"
                "Maintains a stable reference point in spacetime.<br><br>"
                "The anchor is your 'home' - a fixed point you can<br>"
                "return to safely regardless of timeline changes.<br><br>"
                "<b>Functions:</b><br>"
                "• Provides return coordinates<br>"
                "• Measures temporal displacement<br>"
                "• Emergency recovery point"
            ),
            "Safety": (
                "<b>Safety Interlock System</b><br><br>"
                "Monitors for dangerous conditions and can halt<br>"
                "operations automatically.<br><br>"
                "<b>Triggers include:</b><br>"
                "• Paradox risk > 30%<br>"
                "• Causality violation detected<br>"
                "• Field instability<br>"
                "• Manual E-STOP activation<br><br>"
                "When triggered, all temporal operations stop immediately."
            ),
        }

        for module, tooltip in modules.items():
            led = StatusLED(module, tooltip)
            self._leds[module] = led
            layout.addWidget(led)

        layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.state_changed.connect(self._update_status)

    def _update_status(self) -> None:
        """Update status from model."""
        statuses = self._model.get_module_statuses()

        for module, status in statuses.items():
            if module in self._leds:
                self._leds[module].set_status(status)
