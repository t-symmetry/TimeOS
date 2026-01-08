"""Field Monitor Widget - Electromagnetic field display with real-time visualization."""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QProgressBar,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from timeos.gui.models.machine_model import MachineModel


# Configure pyqtgraph
pg.setConfigOptions(antialias=True, background='#0d0d0d', foreground='#808080')


class GaugeBar(QWidget):
    """Horizontal gauge bar with label and value."""

    def __init__(
        self,
        label: str,
        unit: str,
        max_value: float = 100.0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self._max_value = max_value
        self._unit = unit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Label row
        label_layout = QHBoxLayout()
        label_layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setStyleSheet("color: #808080;")
        label_layout.addWidget(self._label)

        self._value_label = QLabel(f"0.0 {unit}")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._value_label.setStyleSheet("color: #00ff88; font-family: monospace;")
        label_layout.addWidget(self._value_label)

        layout.addLayout(label_layout)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(12)
        layout.addWidget(self._bar)

    def set_value(self, value: float) -> None:
        """Set the gauge value."""
        # Update value label with appropriate unit prefix
        if value >= 1e12:
            self._value_label.setText(f"{value/1e12:.2f} T{self._unit}")
        elif value >= 1e9:
            self._value_label.setText(f"{value/1e9:.2f} G{self._unit}")
        elif value >= 1e6:
            self._value_label.setText(f"{value/1e6:.2f} M{self._unit}")
        elif value >= 1e3:
            self._value_label.setText(f"{value/1e3:.2f} k{self._unit}")
        else:
            self._value_label.setText(f"{value:.2f} {self._unit}")

        # Update bar
        percent = min(100, int((value / self._max_value) * 100))
        self._bar.setValue(percent)


class PowerHistoryPlot(pg.PlotWidget):
    """Real-time power consumption history plot."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._history_length = 100
        self._power_history: deque = deque(maxlen=self._history_length)
        self._time_points: deque = deque(maxlen=self._history_length)
        self._time_counter = 0

        self._setup_plot()

    def _setup_plot(self) -> None:
        """Configure the plot."""
        self.setFixedHeight(60)
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideAxis('left')
        self.hideAxis('bottom')

        # Create the plot curve
        self._curve = self.plot(
            pen=pg.mkPen('#00ff88', width=1),
            fillLevel=0,
            brush=pg.mkBrush(0, 255, 136, 30)
        )

        # Initialize with zeros
        for i in range(self._history_length):
            self._power_history.append(0)
            self._time_points.append(i)

    def add_value(self, power: float) -> None:
        """Add a new power reading."""
        self._time_counter += 1
        self._power_history.append(power)
        self._time_points.append(self._time_counter)

        # Update plot
        self._curve.setData(
            list(self._time_points),
            list(self._power_history)
        )

    def clear_history(self) -> None:
        """Clear the history."""
        self._power_history.clear()
        self._time_points.clear()
        self._time_counter = 0
        for i in range(self._history_length):
            self._power_history.append(0)
            self._time_points.append(i)


class FieldMonitor(QGroupBox):
    """Field generator monitoring panel with real-time visualization."""

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("FIELD", parent)

        self._model = model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the monitor UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Field strength (B)
        self._field_gauge = GaugeBar("B:", "T", max_value=100.0)
        layout.addWidget(self._field_gauge)

        # T-symmetry factor with visual indicator
        symmetry_layout = QHBoxLayout()
        sym_label = QLabel("T-sym:")
        sym_label.setStyleSheet("color: #808080;")
        symmetry_layout.addWidget(sym_label)

        self._symmetry_bar = QProgressBar()
        self._symmetry_bar.setRange(0, 100)
        self._symmetry_bar.setValue(0)
        self._symmetry_bar.setTextVisible(False)
        self._symmetry_bar.setFixedHeight(10)
        self._symmetry_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                background-color: #0d0d0d;
            }
            QProgressBar::chunk {
                background-color: #00aaff;
                border-radius: 2px;
            }
        """)
        symmetry_layout.addWidget(self._symmetry_bar)

        self._symmetry_value = QLabel("0.00")
        self._symmetry_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._symmetry_value.setStyleSheet("color: #00aaff; font-family: monospace;")
        self._symmetry_value.setFixedWidth(40)
        symmetry_layout.addWidget(self._symmetry_value)

        layout.addLayout(symmetry_layout)

        # Power consumption
        self._power_gauge = GaugeBar("Power:", "W", max_value=1e12)
        layout.addWidget(self._power_gauge)

        # Power history plot
        self._power_plot = PowerHistoryPlot()
        layout.addWidget(self._power_plot)

        # Status indicator
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setStyleSheet("color: #808080;")
        status_layout.addWidget(status_label)

        self._status_indicator = QLabel("INACTIVE")
        self._status_indicator.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._status_indicator.setStyleSheet("color: #5a5a5a; font-family: monospace;")
        status_layout.addWidget(self._status_indicator)

        layout.addLayout(status_layout)

    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.state_changed.connect(self._update_display)

    def _update_display(self) -> None:
        """Update display from model."""
        state = self._model.get_state()

        # Field strength
        field_strength = state.get("field_strength", 0.0)
        self._field_gauge.set_value(field_strength)

        # T-symmetry
        symmetry = state.get("field_symmetry", 0.0)
        self._symmetry_value.setText(f"{symmetry:.2f}")
        self._symmetry_bar.setValue(int(symmetry * 100))

        # Power
        power = state.get("power_consumption", 0.0)
        self._power_gauge.set_value(power)
        self._power_plot.add_value(power / 1e9)  # Scale to GW for plot

        # Status
        is_active = state.get("field_active", False)
        if is_active:
            self._status_indicator.setText("ACTIVE")
            self._status_indicator.setStyleSheet("color: #00ff88; font-family: monospace;")
        else:
            self._status_indicator.setText("INACTIVE")
            self._status_indicator.setStyleSheet("color: #5a5a5a; font-family: monospace;")
