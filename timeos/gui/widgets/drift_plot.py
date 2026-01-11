"""Drift Plot Widget - Visualize clock drift over time.

Shows clock offset and drift rate from multiple sources with
uncertainty bands and trend lines.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QComboBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont


# Configure pyqtgraph for dark theme
pg.setConfigOptions(antialias=True, background='#0d0d0d', foreground='#808080')

# Clock source colors
CLOCK_COLORS = {
    "ntp": "#00aaff",      # Blue
    "ptp": "#ff8800",      # Orange
    "gps": "#00ff88",      # Green
    "system": "#808080",   # Gray
    "composite": "#aa00ff", # Purple
    "default": "#ffffff",   # White
}


@dataclass
class DriftSample:
    """Single drift measurement sample."""
    timestamp: float  # Monotonic time of measurement
    offset: float     # Offset from reference in seconds
    uncertainty: float  # Uncertainty in offset
    drift_rate: float = 0.0  # Drift rate in ppm


@dataclass
class ClockHistory:
    """History of drift samples for a clock source."""
    source_id: str
    clock_type: str = "unknown"
    samples: Deque[DriftSample] = field(default_factory=lambda: deque(maxlen=1000))
    color: str = "#ffffff"

    def add_sample(self, offset: float, uncertainty: float, drift_rate: float = 0.0) -> None:
        """Add a new sample."""
        self.samples.append(DriftSample(
            timestamp=time.monotonic(),
            offset=offset,
            uncertainty=uncertainty,
            drift_rate=drift_rate,
        ))

    def get_arrays(self, max_age: float = 300.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Get arrays for plotting.

        Args:
            max_age: Maximum sample age in seconds

        Returns:
            Tuple of (times, offsets, uncertainties)
        """
        if not self.samples:
            return np.array([]), np.array([]), np.array([])

        now = time.monotonic()
        cutoff = now - max_age

        times = []
        offsets = []
        uncertainties = []

        for sample in self.samples:
            if sample.timestamp >= cutoff:
                # Convert to relative time (seconds ago)
                times.append(sample.timestamp - now)
                offsets.append(sample.offset * 1e6)  # Convert to microseconds
                uncertainties.append(sample.uncertainty * 1e6)

        return np.array(times), np.array(offsets), np.array(uncertainties)


class DriftPlot(pg.PlotWidget):
    """PyQtGraph-based drift visualization."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._histories: Dict[str, ClockHistory] = {}
        self._plot_items: Dict[str, Dict[str, pg.PlotDataItem]] = {}
        self._show_uncertainty = True
        self._max_age = 300.0  # 5 minutes

        self._setup_plot()

    def _setup_plot(self) -> None:
        """Configure plot appearance."""
        self.setMinimumHeight(200)
        self.setMouseEnabled(x=True, y=True)
        self.setMenuEnabled(False)

        # Configure axes
        self.setLabel('bottom', 'Time', units='s')
        self.setLabel('left', 'Offset', units='µs')
        self.showGrid(x=True, y=True, alpha=0.3)

        # Style axes
        for axis in ['bottom', 'left']:
            self.getAxis(axis).setPen(pg.mkPen('#3a3a3a', width=1))
            self.getAxis(axis).setTextPen('#808080')

        # Zero line
        self._zero_line = pg.InfiniteLine(
            pos=0, angle=0, pen=pg.mkPen('#3a3a3a', width=1, style=Qt.PenStyle.DashLine)
        )
        self.addItem(self._zero_line)

        # Legend
        self._legend = self.addLegend(offset=(10, 10))
        self._legend.setLabelTextColor('#808080')

    def add_clock_source(self, source_id: str, clock_type: str = "unknown") -> None:
        """Add a clock source to track.

        Args:
            source_id: Unique identifier for the clock
            clock_type: Type of clock (ntp, ptp, gps, etc.)
        """
        if source_id in self._histories:
            return

        color = CLOCK_COLORS.get(clock_type.lower(), CLOCK_COLORS["default"])

        self._histories[source_id] = ClockHistory(
            source_id=source_id,
            clock_type=clock_type,
            color=color,
        )

        # Create plot items
        self._plot_items[source_id] = {}

        # Main offset line
        line = self.plot(
            [], [],
            pen=pg.mkPen(color, width=2),
            name=source_id,
        )
        self._plot_items[source_id]["line"] = line

        # Uncertainty fill
        upper = self.plot([], [], pen=None)
        lower = self.plot([], [], pen=None)
        fill = pg.FillBetweenItem(upper, lower, brush=pg.mkBrush(QColor(color).darker(150)))
        fill.setOpacity(0.3)
        self.addItem(fill)
        self._plot_items[source_id]["upper"] = upper
        self._plot_items[source_id]["lower"] = lower
        self._plot_items[source_id]["fill"] = fill

    def remove_clock_source(self, source_id: str) -> None:
        """Remove a clock source."""
        if source_id not in self._histories:
            return

        # Remove plot items
        if source_id in self._plot_items:
            items = self._plot_items.pop(source_id)
            for item in items.values():
                self.removeItem(item)

        del self._histories[source_id]

    def add_sample(
        self,
        source_id: str,
        offset: float,
        uncertainty: float,
        drift_rate: float = 0.0,
    ) -> None:
        """Add a drift sample for a clock source.

        Args:
            source_id: Clock source identifier
            offset: Offset from reference in seconds
            uncertainty: Uncertainty in offset in seconds
            drift_rate: Drift rate in ppm
        """
        if source_id not in self._histories:
            return

        self._histories[source_id].add_sample(offset, uncertainty, drift_rate)
        self._update_plot(source_id)

    def _update_plot(self, source_id: str) -> None:
        """Update plot for a specific source."""
        if source_id not in self._histories:
            return

        history = self._histories[source_id]
        items = self._plot_items.get(source_id, {})

        times, offsets, uncertainties = history.get_arrays(self._max_age)

        if len(times) == 0:
            return

        # Update main line
        if "line" in items:
            items["line"].setData(times, offsets)

        # Update uncertainty bounds
        if self._show_uncertainty and "upper" in items and "lower" in items:
            items["upper"].setData(times, offsets + uncertainties)
            items["lower"].setData(times, offsets - uncertainties)

    def update_all(self) -> None:
        """Update all plots."""
        for source_id in self._histories:
            self._update_plot(source_id)

    def set_uncertainty_visible(self, visible: bool) -> None:
        """Toggle uncertainty band visibility."""
        self._show_uncertainty = visible
        for items in self._plot_items.values():
            if "fill" in items:
                items["fill"].setVisible(visible)
        self.update_all()

    def set_max_age(self, seconds: float) -> None:
        """Set maximum sample age to display."""
        self._max_age = seconds
        self.update_all()

    def clear_history(self) -> None:
        """Clear all sample history."""
        for history in self._histories.values():
            history.samples.clear()
        self.update_all()


class DriftPlotWidget(QGroupBox):
    """Drift visualization widget with controls."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("CLOCK DRIFT", parent)

        self._update_interval = 1000  # ms
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Plot widget
        self._plot = DriftPlot()
        layout.addWidget(self._plot)

        # Control bar
        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)

        # Time range selector
        control_layout.addWidget(QLabel("Range:"))
        self._range_combo = QComboBox()
        self._range_combo.addItems(["1 min", "5 min", "15 min", "1 hour"])
        self._range_combo.setCurrentIndex(1)  # Default 5 min
        self._range_combo.currentIndexChanged.connect(self._on_range_changed)
        control_layout.addWidget(self._range_combo)

        # Uncertainty toggle
        self._uncertainty_cb = QCheckBox("±σ")
        self._uncertainty_cb.setChecked(True)
        self._uncertainty_cb.setToolTip("Show uncertainty bands")
        self._uncertainty_cb.toggled.connect(self._plot.set_uncertainty_visible)
        control_layout.addWidget(self._uncertainty_cb)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(48, 24)
        clear_btn.setToolTip("Clear history")
        clear_btn.clicked.connect(self._plot.clear_history)
        control_layout.addWidget(clear_btn)

        control_layout.addStretch()

        # Status labels
        self._status_label = QLabel("Sources: 0")
        self._status_label.setStyleSheet("color: #808080; font-size: 9pt;")
        control_layout.addWidget(self._status_label)

        layout.addLayout(control_layout)

    def _setup_timer(self) -> None:
        """Set up update timer."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_update)
        self._timer.start(self._update_interval)

    def _on_range_changed(self, index: int) -> None:
        """Handle range selection change."""
        ranges = [60.0, 300.0, 900.0, 3600.0]
        if 0 <= index < len(ranges):
            self._plot.set_max_age(ranges[index])

    def _on_update(self) -> None:
        """Periodic update callback."""
        self._plot.update_all()
        self._status_label.setText(f"Sources: {len(self._plot._histories)}")

    def add_clock_source(self, source_id: str, clock_type: str = "unknown") -> None:
        """Add a clock source to track."""
        self._plot.add_clock_source(source_id, clock_type)

    def add_sample(
        self,
        source_id: str,
        offset: float,
        uncertainty: float,
        drift_rate: float = 0.0,
    ) -> None:
        """Add a drift sample."""
        self._plot.add_sample(source_id, offset, uncertainty, drift_rate)

    def get_plot(self) -> DriftPlot:
        """Get the underlying plot widget."""
        return self._plot
