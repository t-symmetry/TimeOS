"""Clock Status Panel Widget - Clock source status indicators."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QFrame,
    QPushButton,
)
from PySide6.QtCore import Qt, QTimer, Signal

from timeos.gui.widgets.status_panel import StatusLED


class ClockSourceWidget(QWidget):
    """Widget showing a single clock source with quality metrics."""

    def __init__(
        self,
        source_id: str,
        clock_type: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._source_id = source_id
        self._clock_type = clock_type

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header row with LED and name
        header = QHBoxLayout()
        header.setSpacing(8)

        # LED indicator
        self._led = QLabel()
        self._led.setFixedSize(10, 10)
        self._led.setStyleSheet(self._led_style("#5a5a5a"))
        header.addWidget(self._led)

        # Source name
        self._name_label = QLabel(self._source_id)
        self._name_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        header.addWidget(self._name_label)

        # Type badge
        self._type_label = QLabel(self._clock_type)
        self._type_label.setStyleSheet(
            "color: #888888; font-size: 10px; font-family: monospace;"
        )
        header.addWidget(self._type_label)

        header.addStretch()

        # Status text
        self._status_label = QLabel("OFFLINE")
        self._status_label.setStyleSheet("color: #5a5a5a; font-family: monospace;")
        header.addWidget(self._status_label)

        layout.addLayout(header)

        # Metrics row
        metrics = QHBoxLayout()
        metrics.setSpacing(16)

        # Offset
        self._offset_label = QLabel("Offset: --")
        self._offset_label.setStyleSheet("color: #888888; font-size: 10px;")
        self._offset_label.setToolTip("Offset from reference clock")
        metrics.addWidget(self._offset_label)

        # Uncertainty
        self._uncertainty_label = QLabel("±--")
        self._uncertainty_label.setStyleSheet("color: #888888; font-size: 10px;")
        self._uncertainty_label.setToolTip("Current uncertainty bound")
        metrics.addWidget(self._uncertainty_label)

        # Stratum
        self._stratum_label = QLabel("Stratum: --")
        self._stratum_label.setStyleSheet("color: #888888; font-size: 10px;")
        self._stratum_label.setToolTip("NTP stratum level (1=reference, lower=better)")
        metrics.addWidget(self._stratum_label)

        metrics.addStretch()

        layout.addLayout(metrics)

    def update_status(
        self,
        status: str,
        offset: float = 0.0,
        uncertainty: float = 0.0,
        stratum: int = 16,
        quality_score: float = 0.0,
    ) -> None:
        """Update the clock status display.

        Args:
            status: Status string (SYNCED, FREERUN, FAULT, etc.)
            offset: Offset from reference in seconds
            uncertainty: Uncertainty in seconds
            stratum: NTP stratum level
            quality_score: Quality score 0-1
        """
        # Update LED color based on status
        status_upper = status.upper()
        color = self._status_color(status_upper, quality_score)
        self._led.setStyleSheet(self._led_style(color))

        # Update status text
        self._status_label.setText(status_upper)
        self._status_label.setStyleSheet(f"color: {color}; font-family: monospace;")

        # Update metrics
        self._offset_label.setText(f"Offset: {self._format_time(offset)}")
        self._uncertainty_label.setText(f"±{self._format_time(uncertainty)}")
        self._stratum_label.setText(f"Stratum: {stratum}")

    def _status_color(self, status: str, quality_score: float) -> str:
        """Get color for status."""
        if status in ("SYNCED", "READY"):
            if quality_score > 0.8:
                return "#00ff88"  # Green
            elif quality_score > 0.5:
                return "#88ff00"  # Yellow-green
            else:
                return "#ffaa00"  # Orange
        elif status in ("SYNCING", "HOLDOVER"):
            return "#ffff00"  # Yellow
        elif status in ("DEGRADED",):
            return "#ffaa00"  # Orange
        elif status in ("FREERUN",):
            return "#ff8800"  # Dark orange
        elif status in ("FAULT", "ERROR"):
            return "#ff4444"  # Red
        else:
            return "#5a5a5a"  # Gray

    def _format_time(self, seconds: float) -> str:
        """Format time value with appropriate units."""
        if seconds == float('inf') or seconds != seconds:  # NaN check
            return "--"

        abs_s = abs(seconds)
        if abs_s == 0:
            return "0"
        elif abs_s < 1e-9:
            return f"{seconds*1e12:.1f} ps"
        elif abs_s < 1e-6:
            return f"{seconds*1e9:.1f} ns"
        elif abs_s < 1e-3:
            return f"{seconds*1e6:.1f} µs"
        elif abs_s < 1:
            return f"{seconds*1e3:.1f} ms"
        else:
            return f"{seconds:.3f} s"

    def _led_style(self, color: str) -> str:
        """Generate LED stylesheet."""
        return f"""
            background-color: {color};
            border-radius: 5px;
            border: 1px solid {color};
        """


class ClockStatusPanel(QGroupBox):
    """Panel showing all clock sources with quality indicators."""

    refresh_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("CLOCK SOURCES", parent)

        self._clock_widgets: Dict[str, ClockSourceWidget] = {}
        self._registry = None

        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Clock sources container
        self._clocks_layout = QVBoxLayout()
        self._clocks_layout.setSpacing(4)
        layout.addLayout(self._clocks_layout)

        # Add placeholder if no clocks
        self._placeholder = QLabel("No clock sources")
        self._placeholder.setStyleSheet("color: #666666; font-style: italic;")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clocks_layout.addWidget(self._placeholder)

        layout.addStretch()

        # Footer with best clock and refresh button
        footer = QHBoxLayout()

        self._best_clock_label = QLabel("Best: --")
        self._best_clock_label.setStyleSheet("color: #00ff88; font-size: 10px;")
        self._best_clock_label.setToolTip("Currently selected best clock source")
        footer.addWidget(self._best_clock_label)

        footer.addStretch()

        self._last_update_label = QLabel("")
        self._last_update_label.setStyleSheet("color: #666666; font-size: 10px;")
        footer.addWidget(self._last_update_label)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setToolTip("Refresh clock sources")
        refresh_btn.clicked.connect(self._on_refresh_clicked)
        footer.addWidget(refresh_btn)

        layout.addLayout(footer)

    def _setup_timer(self) -> None:
        """Set up refresh timer."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_clocks)
        self._refresh_timer.start(1000)  # 1 Hz refresh

    def set_registry(self, registry) -> None:
        """Set the clock registry to monitor.

        Args:
            registry: ClockRegistry instance
        """
        self._registry = registry
        self._refresh_clocks()

    def _refresh_clocks(self) -> None:
        """Refresh clock displays from registry."""
        if self._registry is None:
            # Use default clocks
            self._show_default_clocks()
            return

        # Hide placeholder
        self._placeholder.hide()

        # Update or create widgets for each clock
        for clock in self._registry:
            source_id = clock.source_id

            if source_id not in self._clock_widgets:
                # Create new widget
                widget = ClockSourceWidget(
                    source_id=source_id,
                    clock_type=clock.clock_type.value,
                    parent=self,
                )
                self._clock_widgets[source_id] = widget
                self._clocks_layout.insertWidget(
                    self._clocks_layout.count() - 1,  # Before stretch
                    widget
                )

            # Update status
            quality = clock.get_quality()
            self._clock_widgets[source_id].update_status(
                status=clock.status.name,
                offset=quality.offset,
                uncertainty=quality.estimated_error,
                stratum=quality.stratum,
                quality_score=quality.quality_score,
            )

        # Update best clock
        best = self._registry.get_best()
        if best:
            self._best_clock_label.setText(f"Best: {best.source_id}")
        else:
            self._best_clock_label.setText("Best: --")

        # Update timestamp
        self._last_update_label.setText(
            datetime.now().strftime("%H:%M:%S")
        )

    def _show_default_clocks(self) -> None:
        """Show default system clocks when no registry is set."""
        try:
            from timeos.clocks import (
                ClockRegistry,
                RealtimeClock,
                MonotonicClock,
                NTPClock,
            )

            # Create default registry
            self._registry = ClockRegistry()

            # Add system clocks
            self._registry.register(RealtimeClock())
            self._registry.register(MonotonicClock())

            # Try NTP
            try:
                ntp = NTPClock()
                if ntp.ntp_daemon:
                    self._registry.register(ntp)
            except Exception:
                pass

            self._refresh_clocks()

        except ImportError:
            # Clocks module not available
            self._placeholder.setText("Clock module not available")
            self._placeholder.show()

    def _on_refresh_clicked(self) -> None:
        """Handle refresh button click."""
        if self._registry:
            self._registry.refresh_all()
        self._refresh_clocks()
        self.refresh_requested.emit()

    def stop(self) -> None:
        """Stop the refresh timer."""
        self._refresh_timer.stop()
