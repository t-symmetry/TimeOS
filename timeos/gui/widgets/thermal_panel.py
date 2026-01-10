"""Thermal Panel - Temperature monitoring and quench prediction visualization."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QGridLayout,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False


class TemperatureGauge(QWidget):
    """Visual temperature gauge with color gradient."""

    def __init__(
        self,
        min_temp: float = 0.0,
        max_temp: float = 10.0,
        critical_temp: float = 9.0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._critical_temp = critical_temp
        self._current_temp = 4.2
        self._target_temp = 4.2

        self.setMinimumSize(60, 150)
        self.setMaximumWidth(80)

    def set_temperature(self, temp: float) -> None:
        """Set current temperature."""
        self._current_temp = temp
        self.update()

    def set_target(self, temp: float) -> None:
        """Set target temperature."""
        self._target_temp = temp
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 10
        gauge_w = 30
        gauge_x = (w - gauge_w) // 2

        # Background
        painter.fillRect(0, 0, w, h, QColor("#1a1a2e"))

        # Gauge outline
        painter.setPen(QPen(QColor("#444466"), 2))
        painter.drawRect(gauge_x, margin, gauge_w, h - 2 * margin)

        # Temperature fill
        temp_range = self._max_temp - self._min_temp
        temp_frac = (self._current_temp - self._min_temp) / temp_range
        temp_frac = max(0, min(1, temp_frac))

        fill_h = int((h - 2 * margin - 4) * temp_frac)
        fill_y = h - margin - 2 - fill_h

        # Color based on temperature
        if self._current_temp >= self._critical_temp:
            color = QColor("#ff4444")
        elif self._current_temp >= self._critical_temp * 0.8:
            color = QColor("#ffaa00")
        elif self._current_temp >= self._critical_temp * 0.5:
            color = QColor("#44aaff")
        else:
            color = QColor("#00ff88")

        painter.fillRect(gauge_x + 2, fill_y, gauge_w - 4, fill_h, color)

        # Critical line
        crit_frac = (self._critical_temp - self._min_temp) / temp_range
        crit_y = h - margin - int((h - 2 * margin) * crit_frac)
        painter.setPen(QPen(QColor("#ff4444"), 2, Qt.PenStyle.DashLine))
        painter.drawLine(gauge_x - 5, crit_y, gauge_x + gauge_w + 5, crit_y)

        # Target line
        target_frac = (self._target_temp - self._min_temp) / temp_range
        target_y = h - margin - int((h - 2 * margin) * target_frac)
        painter.setPen(QPen(QColor("#00ff88"), 2))
        painter.drawLine(gauge_x - 5, target_y, gauge_x + gauge_w + 5, target_y)

        # Labels
        painter.setPen(QColor("#ffffff"))
        font = QFont("Monospace", 8)
        painter.setFont(font)

        # Current temp
        painter.drawText(
            0, h // 2 - 20, w, 20,
            Qt.AlignmentFlag.AlignCenter,
            f"{self._current_temp:.2f} K"
        )

        # Min/max
        painter.drawText(
            0, h - margin + 2, w, 15,
            Qt.AlignmentFlag.AlignCenter,
            f"{self._min_temp:.0f}"
        )
        painter.drawText(
            0, 0, w, 15,
            Qt.AlignmentFlag.AlignCenter,
            f"{self._max_temp:.0f}"
        )


class ThermalPanel(QWidget):
    """Panel for thermal system monitoring.

    Features:
    - Temperature display with gauge
    - Quench risk indicator
    - Cooling system status
    - Temperature history plot
    - Thermal margins
    """

    # Signals
    quench_warning = Signal(float)  # risk level
    temperature_alert = Signal(float, str)  # temp, message

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._temp_history: deque = deque(maxlen=100)
        self._time_history: deque = deque(maxlen=100)
        self._start_time = 0.0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Title
        title = QLabel("Thermal System")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Main content
        content = QHBoxLayout()

        # Left: Temperature gauge
        self._gauge = TemperatureGauge(
            min_temp=0.0,
            max_temp=12.0,
            critical_temp=9.2,
        )
        content.addWidget(self._gauge)

        # Right: Stats and plot
        right_layout = QVBoxLayout()

        # Temperature readouts
        temp_group = QGroupBox("Temperature")
        temp_layout = QGridLayout(temp_group)

        temp_layout.addWidget(QLabel("Current:"), 0, 0)
        self._current_temp_label = QLabel("4.20 K")
        self._current_temp_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; color: #00ff88;"
        )
        temp_layout.addWidget(self._current_temp_label, 0, 1)

        temp_layout.addWidget(QLabel("Target:"), 1, 0)
        self._target_temp_label = QLabel("4.20 K")
        temp_layout.addWidget(self._target_temp_label, 1, 1)

        temp_layout.addWidget(QLabel("Critical:"), 2, 0)
        self._critical_temp_label = QLabel("9.20 K")
        self._critical_temp_label.setStyleSheet("color: #ff4444;")
        temp_layout.addWidget(self._critical_temp_label, 2, 1)

        right_layout.addWidget(temp_group)

        # Quench risk
        risk_group = QGroupBox("Quench Risk")
        risk_layout = QVBoxLayout(risk_group)

        self._risk_bar = QProgressBar()
        self._risk_bar.setRange(0, 100)
        self._risk_bar.setValue(0)
        self._risk_bar.setFormat("%v%")
        self._risk_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444466;
                border-radius: 3px;
                background-color: #1a1a2e;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00ff88;
            }
        """)
        risk_layout.addWidget(self._risk_bar)

        self._risk_label = QLabel("NOMINAL")
        self._risk_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._risk_label.setStyleSheet("color: #00ff88; font-weight: bold;")
        risk_layout.addWidget(self._risk_label)

        right_layout.addWidget(risk_group)

        # Cooling status
        cooling_group = QGroupBox("Cooling System")
        cooling_layout = QGridLayout(cooling_group)

        cooling_layout.addWidget(QLabel("State:"), 0, 0)
        self._cooling_state_label = QLabel("COLD")
        self._cooling_state_label.setStyleSheet("color: #44aaff;")
        cooling_layout.addWidget(self._cooling_state_label, 0, 1)

        cooling_layout.addWidget(QLabel("Power:"), 1, 0)
        self._cooling_power_label = QLabel("0.0 W")
        cooling_layout.addWidget(self._cooling_power_label, 1, 1)

        cooling_layout.addWidget(QLabel("Margin:"), 2, 0)
        self._margin_label = QLabel("5.00 K")
        self._margin_label.setStyleSheet("color: #00ff88;")
        cooling_layout.addWidget(self._margin_label, 2, 1)

        right_layout.addWidget(cooling_group)

        content.addLayout(right_layout)
        layout.addLayout(content)

        # Temperature plot
        if PYQTGRAPH_AVAILABLE:
            plot_group = QGroupBox("Temperature History")
            plot_layout = QVBoxLayout(plot_group)

            self._plot = pg.PlotWidget()
            self._plot.setBackground("#1a1a2e")
            self._plot.setMaximumHeight(100)
            self._plot.showGrid(x=True, y=True, alpha=0.3)
            self._plot.setLabel("left", "T", units="K")
            self._plot.setLabel("bottom", "Time", units="s")

            self._temp_curve = self._plot.plot(
                pen=pg.mkPen("#00ff88", width=2)
            )

            # Critical line
            self._crit_line = pg.InfiniteLine(
                pos=9.2,
                angle=0,
                pen=pg.mkPen("#ff4444", width=1, style=Qt.PenStyle.DashLine),
            )
            self._plot.addItem(self._crit_line)

            plot_layout.addWidget(self._plot)
            layout.addWidget(plot_group)

        # Sensor readings
        sensor_group = QGroupBox("Sensors")
        sensor_layout = QGridLayout(sensor_group)

        sensors = [
            ("Magnet Core", "mag_core"),
            ("Cryostat", "cryostat"),
            ("Shield", "shield"),
            ("Ambient", "ambient"),
        ]

        self._sensor_labels = {}
        for i, (name, key) in enumerate(sensors):
            row = i // 2
            col = (i % 2) * 2

            sensor_layout.addWidget(QLabel(f"{name}:"), row, col)
            label = QLabel("-- K")
            label.setStyleSheet("font-family: monospace;")
            sensor_layout.addWidget(label, row, col + 1)
            self._sensor_labels[key] = label

        layout.addWidget(sensor_group)

    def update_thermal(
        self,
        temperature: float,
        quench_risk: float,
        cooling_state: str = "cold",
        cooling_power: float = 0.0,
        target_temp: float = 4.2,
        critical_temp: float = 9.2,
        sensors: dict[str, float] | None = None,
    ) -> None:
        """Update thermal display.

        Args:
            temperature: Current temperature in Kelvin
            quench_risk: Quench risk (0.0 to 1.0)
            cooling_state: Cooling system state
            cooling_power: Cooling power in Watts
            target_temp: Target temperature
            critical_temp: Critical temperature
            sensors: Individual sensor readings
        """
        # Update gauge
        self._gauge.set_temperature(temperature)
        self._gauge.set_target(target_temp)

        # Update labels
        self._current_temp_label.setText(f"{temperature:.2f} K")
        self._target_temp_label.setText(f"{target_temp:.2f} K")
        self._critical_temp_label.setText(f"{critical_temp:.2f} K")

        # Color current temp based on risk
        if quench_risk > 0.5:
            color = "#ff4444"
        elif quench_risk > 0.1:
            color = "#ffaa00"
        else:
            color = "#00ff88"
        self._current_temp_label.setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {color};"
        )

        # Quench risk
        risk_pct = int(quench_risk * 100)
        self._risk_bar.setValue(risk_pct)

        if quench_risk > 0.5:
            self._risk_label.setText("CRITICAL")
            self._risk_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self._risk_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #ff4444; }
            """)
            self.quench_warning.emit(quench_risk)
        elif quench_risk > 0.1:
            self._risk_label.setText("ELEVATED")
            self._risk_label.setStyleSheet("color: #ffaa00; font-weight: bold;")
            self._risk_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #ffaa00; }
            """)
        else:
            self._risk_label.setText("NOMINAL")
            self._risk_label.setStyleSheet("color: #00ff88; font-weight: bold;")
            self._risk_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #00ff88; }
            """)

        # Cooling
        self._cooling_state_label.setText(cooling_state.upper())
        self._cooling_power_label.setText(f"{cooling_power:.1f} W")

        margin = critical_temp - temperature
        self._margin_label.setText(f"{margin:.2f} K")
        if margin < 1.0:
            self._margin_label.setStyleSheet("color: #ff4444;")
        elif margin < 2.0:
            self._margin_label.setStyleSheet("color: #ffaa00;")
        else:
            self._margin_label.setStyleSheet("color: #00ff88;")

        # Sensors
        if sensors:
            for key, value in sensors.items():
                if key in self._sensor_labels:
                    self._sensor_labels[key].setText(f"{value:.2f} K")

        # History plot
        if PYQTGRAPH_AVAILABLE:
            import time
            if not self._start_time:
                self._start_time = time.time()

            t = time.time() - self._start_time
            self._time_history.append(t)
            self._temp_history.append(temperature)

            self._temp_curve.setData(
                list(self._time_history),
                list(self._temp_history),
            )

    def set_critical_temp(self, temp: float) -> None:
        """Set the critical temperature line."""
        if PYQTGRAPH_AVAILABLE:
            self._crit_line.setPos(temp)
