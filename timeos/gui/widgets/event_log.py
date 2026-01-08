"""Event Log Widget - Scrolling event log display."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QGroupBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QColor

from timeos.gui.models.machine_model import MachineModel


class EventLogWidget(QGroupBox):
    """Scrolling event log display."""

    LEVEL_COLORS = {
        "info": "#e0e0e0",
        "warning": "#ffaa00",
        "error": "#ff4444",
        "critical": "#ff0000",
    }

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("EVENT LOG", parent)

        self._model = model
        self._setup_ui()
        self._connect_signals()

        # Load existing events
        self._load_existing_events()

    def _setup_ui(self) -> None:
        """Set up the log UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d0d;
                border: 1px solid #3a3a3a;
                font-family: monospace;
                font-size: 9pt;
            }
        """)
        layout.addWidget(self._log_view)

    def _connect_signals(self) -> None:
        """Connect model signals."""
        self._model.event_logged.connect(self._on_event)

    def _load_existing_events(self) -> None:
        """Load existing events from model."""
        for event in self._model.get_events():
            self._append_event(event)

    def _on_event(self, event: dict) -> None:
        """Handle new event."""
        self._append_event(event)

    def _append_event(self, event: dict) -> None:
        """Append event to log display."""
        timestamp = event.get("timestamp", "")
        if isinstance(timestamp, str):
            # Parse ISO format and extract time
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%H:%M:%S")
            except ValueError:
                time_str = timestamp[:8]
        else:
            time_str = str(timestamp)[:8]

        message = event.get("message", "")
        level = event.get("level", "info")
        color = self.LEVEL_COLORS.get(level, "#e0e0e0")

        # Format the log line
        html = f'<span style="color: #808080;">[{time_str}]</span> '
        html += f'<span style="color: {color};">{message}</span><br>'

        # Append to log
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)
        self._log_view.insertHtml(html)

        # Auto-scroll to bottom
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        """Clear the log display."""
        self._log_view.clear()
