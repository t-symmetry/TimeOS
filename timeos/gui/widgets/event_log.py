"""Event Log Widget - Scrolling event log display with filtering."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QGroupBox,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QColor

from timeos.gui.models.machine_model import MachineModel


class EventLogWidget(QGroupBox):
    """Scrolling event log display with level filtering."""

    LEVEL_COLORS = {
        "info": "#e0e0e0",
        "warning": "#ffaa00",
        "error": "#ff4444",
        "critical": "#ff0000",
    }

    def __init__(self, model: MachineModel, parent: QWidget | None = None):
        super().__init__("EVENT LOG", parent)

        self._model = model
        self._events: list[dict] = []  # Store all events for filtering
        self._active_filters: set[str] = {"info", "warning", "error", "critical"}
        self._setup_ui()
        self._connect_signals()

        # Load existing events
        self._load_existing_events()

    def _setup_ui(self) -> None:
        """Set up the log UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Filter toolbar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(4)

        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: #808080;")
        filter_layout.addWidget(filter_label)

        # Filter buttons
        self._filter_buttons: dict[str, QPushButton] = {}
        for level, color in self.LEVEL_COLORS.items():
            btn = QPushButton(level.upper())
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFixedHeight(20)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1a1a1a;
                    border: 1px solid {color};
                    color: {color};
                    padding: 2px 8px;
                    font-size: 8pt;
                }}
                QPushButton:checked {{
                    background-color: {color};
                    color: #0d0d0d;
                }}
                QPushButton:hover {{
                    border-width: 2px;
                }}
            """)
            btn.toggled.connect(lambda checked, lvl=level: self._on_filter_toggle(lvl, checked))
            filter_layout.addWidget(btn)
            self._filter_buttons[level] = btn

        filter_layout.addStretch()

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(20)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                color: #808080;
                padding: 2px 8px;
                font-size: 8pt;
            }
            QPushButton:hover {
                border-color: #5a5a5a;
            }
        """)
        clear_btn.clicked.connect(self.clear)
        filter_layout.addWidget(clear_btn)

        # Event count
        self._count_label = QLabel("0 events")
        self._count_label.setStyleSheet("color: #5a5a5a; font-size: 8pt;")
        filter_layout.addWidget(self._count_label)

        layout.addLayout(filter_layout)

        # Log view
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
            self._events.append(event)
            self._append_event(event)
        self._update_count()

    def _on_event(self, event: dict) -> None:
        """Handle new event."""
        self._events.append(event)
        self._append_event(event)
        self._update_count()

    def _on_filter_toggle(self, level: str, checked: bool) -> None:
        """Handle filter button toggle."""
        if checked:
            self._active_filters.add(level)
        else:
            self._active_filters.discard(level)
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display with current filters applied."""
        self._log_view.clear()
        for event in self._events:
            self._append_event(event)
        self._update_count()

    def _update_count(self) -> None:
        """Update the event count label."""
        visible = sum(
            1 for e in self._events
            if e.get("level", "info") in self._active_filters
        )
        total = len(self._events)
        if visible == total:
            self._count_label.setText(f"{total} events")
        else:
            self._count_label.setText(f"{visible}/{total} events")

    def _append_event(self, event: dict) -> None:
        """Append event to log display if it passes filters."""
        level = event.get("level", "info")

        # Check if this level is filtered
        if level not in self._active_filters:
            return

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
        """Clear the log display and stored events."""
        self._events.clear()
        self._log_view.clear()
        self._update_count()
