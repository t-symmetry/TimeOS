"""Event Details Dialog - Display detailed event information."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QTextEdit,
    QTabWidget,
    QWidget,
)
from PySide6.QtCore import Qt


class EventDetailsDialog(QDialog):
    """Dialog showing detailed information about a timeline event."""

    def __init__(self, event: dict, parent=None):
        super().__init__(parent)

        self._event = event
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Event Details")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Event header
        header_layout = QHBoxLayout()

        event_type = self._event.get("type", "unknown")
        type_label = QLabel(f"Event Type: {event_type}")
        type_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #00ff88;")
        header_layout.addWidget(type_label)

        header_layout.addStretch()

        event_id = self._event.get("id", "N/A")[:8]
        id_label = QLabel(f"ID: {event_id}...")
        id_label.setStyleSheet("color: #808080; font-family: monospace;")
        header_layout.addWidget(id_label)

        layout.addLayout(header_layout)

        # Tab widget for different views
        tabs = QTabWidget()

        # Overview tab
        overview_tab = self._create_overview_tab()
        tabs.addTab(overview_tab, "Overview")

        # Payload tab
        payload_tab = self._create_payload_tab()
        tabs.addTab(payload_tab, "Payload")

        # Causality tab
        causality_tab = self._create_causality_tab()
        tabs.addTab(causality_tab, "Causality")

        layout.addWidget(tabs)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setMinimumSize(80, 32)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_overview_tab(self) -> QWidget:
        """Create the overview tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Timestamp section
        timestamp_group = QGroupBox("Timestamp")
        ts_layout = QVBoxLayout(timestamp_group)

        stamp = self._event.get("stamp", {})
        self._add_info_row(ts_layout, "Time:", f"{stamp.get('t', 0.0):.6f} s")
        self._add_info_row(ts_layout, "Uncertainty:", f"±{stamp.get('t_uncertainty', 0.0):.9f} s")
        self._add_info_row(ts_layout, "Frame:", stamp.get("frame_id", "unknown"))
        self._add_info_row(ts_layout, "Clock:", stamp.get("clock_id", "N/A"))

        layout.addWidget(timestamp_group)

        # Metadata section
        meta_group = QGroupBox("Metadata")
        meta_layout = QVBoxLayout(meta_group)

        self._add_info_row(meta_layout, "Branch:", self._event.get("branch_id", "main"))
        self._add_info_row(meta_layout, "Sequence:", str(self._event.get("sequence", 0)))
        self._add_info_row(meta_layout, "Created:", self._event.get("created_at", "N/A"))

        layout.addWidget(meta_group)

        layout.addStretch()

        return widget

    def _create_payload_tab(self) -> QWidget:
        """Create the payload tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        payload = self._event.get("payload", {})

        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d0d;
                border: 1px solid #3a3a3a;
                font-family: monospace;
                color: #e0e0e0;
            }
        """)

        try:
            formatted = json.dumps(payload, indent=2, default=str)
        except Exception:
            formatted = str(payload)

        text.setPlainText(formatted)
        layout.addWidget(text)

        return widget

    def _create_causality_tab(self) -> QWidget:
        """Create the causality tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Parents section
        parents_group = QGroupBox("Causal Parents")
        parents_layout = QVBoxLayout(parents_group)

        parents = self._event.get("causal_parents", [])
        if parents:
            for parent_id in parents:
                label = QLabel(f"• {parent_id[:16]}...")
                label.setStyleSheet("color: #00ff88; font-family: monospace;")
                parents_layout.addWidget(label)
        else:
            label = QLabel("No causal parents (root event)")
            label.setStyleSheet("color: #808080;")
            parents_layout.addWidget(label)

        layout.addWidget(parents_group)

        # Constraints section
        constraints_group = QGroupBox("Constraints")
        constraints_layout = QVBoxLayout(constraints_group)

        constraints = self._event.get("constraints", [])
        if constraints:
            for constraint in constraints:
                label = QLabel(f"• {constraint}")
                label.setStyleSheet("color: #ffaa00;")
                constraints_layout.addWidget(label)
        else:
            label = QLabel("No special constraints")
            label.setStyleSheet("color: #808080;")
            constraints_layout.addWidget(label)

        layout.addWidget(constraints_group)

        layout.addStretch()

        return widget

    def _add_info_row(self, layout: QVBoxLayout, label: str, value: str) -> None:
        """Add an info row to a layout."""
        row = QHBoxLayout()

        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #808080;")
        label_widget.setMinimumWidth(100)
        row.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("color: #00ff88; font-family: monospace;")
        row.addWidget(value_widget)

        row.addStretch()

        layout.addLayout(row)
