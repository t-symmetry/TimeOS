"""Timeline View Widget - Visual timeline with events and branches."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QFrame,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont

from timeos.gui.models.machine_model import MachineModel


class TimelineCanvas(QWidget):
    """Canvas widget for drawing the timeline."""

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__(parent)

        self._model = model
        self._events: list[dict] = []
        self._current_time = 0.0
        self._anchor_time = 0.0
        self._view_start = -10.0
        self._view_end = 10.0

        self.setMinimumHeight(120)
        self.setStyleSheet("background-color: #0d0d0d;")

    def set_events(self, events: list[dict]) -> None:
        """Set events to display."""
        self._events = events
        self.update()

    def set_current_time(self, t: float) -> None:
        """Set current time marker."""
        self._current_time = t
        self.update()

    def set_anchor_time(self, t: float | None) -> None:
        """Set anchor time marker."""
        self._anchor_time = t if t is not None else 0.0
        self.update()

    def set_view_range(self, start: float, end: float) -> None:
        """Set the visible time range."""
        self._view_start = start
        self._view_end = end
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the timeline."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 40
        timeline_y = h // 2

        # Background
        painter.fillRect(0, 0, w, h, QColor("#0d0d0d"))

        # Timeline axis
        pen = QPen(QColor("#3a3a3a"), 2)
        painter.setPen(pen)
        painter.drawLine(margin, timeline_y, w - margin, timeline_y)

        # Arrow at end
        arrow_x = w - margin
        painter.drawLine(arrow_x, timeline_y, arrow_x - 10, timeline_y - 5)
        painter.drawLine(arrow_x, timeline_y, arrow_x - 10, timeline_y + 5)

        # Time labels and ticks
        painter.setPen(QPen(QColor("#5a5a5a"), 1))
        font = QFont("Monospace", 8)
        painter.setFont(font)

        time_range = self._view_end - self._view_start
        if time_range <= 0:
            time_range = 20.0

        # Draw ticks
        tick_count = 10
        for i in range(tick_count + 1):
            t = self._view_start + (time_range * i / tick_count)
            x = margin + ((t - self._view_start) / time_range) * (w - 2 * margin)

            # Tick
            painter.drawLine(int(x), timeline_y - 5, int(x), timeline_y + 5)

            # Label
            label = f"{t:.1f}"
            painter.drawText(int(x) - 15, timeline_y + 20, label)

        # Anchor marker (diamond)
        if self._anchor_time is not None:
            anchor_x = margin + (
                (self._anchor_time - self._view_start) / time_range
            ) * (w - 2 * margin)

            if margin <= anchor_x <= w - margin:
                painter.setPen(QPen(QColor("#00aaff"), 2))
                painter.setBrush(QBrush(QColor("#00aaff")))

                # Diamond shape
                points = [
                    QPointF(anchor_x, timeline_y - 12),
                    QPointF(anchor_x + 8, timeline_y),
                    QPointF(anchor_x, timeline_y + 12),
                    QPointF(anchor_x - 8, timeline_y),
                ]
                painter.drawPolygon(points)

                # Label
                painter.setPen(QPen(QColor("#00aaff"), 1))
                painter.drawText(int(anchor_x) - 20, timeline_y - 20, "ANCHOR")

        # Current position marker (circle with glow)
        current_x = margin + (
            (self._current_time - self._view_start) / time_range
        ) * (w - 2 * margin)

        if margin <= current_x <= w - margin:
            # Glow effect
            for i in range(3, 0, -1):
                alpha = 50 - i * 15
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(0, 255, 136, alpha)))
                painter.drawEllipse(
                    QPointF(current_x, timeline_y),
                    8 + i * 3,
                    8 + i * 3,
                )

            # Main marker
            painter.setPen(QPen(QColor("#00ff88"), 2))
            painter.setBrush(QBrush(QColor("#00ff88")))
            painter.drawEllipse(QPointF(current_x, timeline_y), 8, 8)

            # Label
            painter.setPen(QPen(QColor("#00ff88"), 1))
            painter.drawText(int(current_x) - 10, timeline_y - 20, "NOW")

        # Draw events as small circles on the timeline
        painter.setPen(QPen(QColor("#808080"), 1))
        painter.setBrush(QBrush(QColor("#404040")))

        for evt in self._events:
            evt_time = evt.get("time", 0.0)
            evt_x = margin + (
                (evt_time - self._view_start) / time_range
            ) * (w - 2 * margin)

            if margin <= evt_x <= w - margin:
                painter.drawEllipse(QPointF(evt_x, timeline_y), 5, 5)

        # "t" label
        painter.setPen(QPen(QColor("#808080"), 1))
        painter.drawText(w - margin + 5, timeline_y + 5, "t")


class TimelineView(QGroupBox):
    """Timeline visualization widget."""

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("TIMELINE", parent)

        self._model = model
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the timeline UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Canvas
        self._canvas = TimelineCanvas(self._model)
        layout.addWidget(self._canvas)

        # Info bar
        info_layout = QHBoxLayout()

        self._range_label = QLabel("View: -10.0s to +10.0s")
        self._range_label.setStyleSheet("color: #808080; font-size: 9pt;")
        info_layout.addWidget(self._range_label)

        info_layout.addStretch()

        self._event_count = QLabel("Events: 0")
        self._event_count.setStyleSheet("color: #808080; font-size: 9pt;")
        info_layout.addWidget(self._event_count)

        layout.addLayout(info_layout)

    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.state_changed.connect(self._update_display)

    def _update_display(self) -> None:
        """Update timeline from model."""
        state = self._model.get_state()

        current_time = state.get("current_time", 0.0)
        anchor_time = state.get("anchor_time")

        self._canvas.set_current_time(current_time)
        self._canvas.set_anchor_time(anchor_time)

        # Auto-adjust view range based on current time
        view_start = current_time - 10.0
        view_end = current_time + 10.0
        self._canvas.set_view_range(view_start, view_end)
        self._range_label.setText(f"View: {view_start:.1f}s to {view_end:.1f}s")

        # Update event count
        events = self._model.get_events()
        self._event_count.setText(f"Events: {len(events)}")
