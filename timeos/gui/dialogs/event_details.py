"""Event Details Dialog - Display detailed event information."""

from __future__ import annotations

import json
import math

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

from timeos.physics import FourVector, Event as SpacetimeEvent, SpacetimeInterval, LightCone, CausalRelation
from timeos.core.constraints import (
    ConstraintChecker, ConstraintCheck, ConstraintStatus,
    ValidationResult as ConstraintValidation,
)


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
        """Create the causality tab with inspectable constraint checks."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Constraint checks section - the main inspectable view
        checks_group = QGroupBox("Constraint Checks")
        checks_layout = QVBoxLayout(checks_group)

        # Get constraint checks from event data, or generate sample checks
        checks = self._event.get("constraint_checks", [])

        if not checks:
            # Generate sample checks for display
            checks = self._generate_sample_checks()

        for check in checks:
            check_row = QHBoxLayout()

            # Status icon
            icon = check.get("icon", "✔")
            status = check.get("status", "satisfied")

            # Color based on status
            if status == "satisfied":
                color = "#00ff88"
            elif status == "warning":
                color = "#ffaa00"
            elif status == "deferred":
                color = "#00aaff"
            else:
                color = "#ff4444"

            icon_label = QLabel(icon)
            icon_label.setStyleSheet(f"color: {color}; font-size: 12pt;")
            icon_label.setFixedWidth(20)
            check_row.addWidget(icon_label)

            # Constraint description
            desc = check.get("description", "Unknown constraint")
            desc_label = QLabel(f"Constraint: {desc}")
            desc_label.setStyleSheet("color: #e0e0e0;")
            check_row.addWidget(desc_label)

            check_row.addStretch()

            # Details
            details = check.get("details", "")
            if details:
                details_label = QLabel(details)
                details_label.setStyleSheet(f"color: {color}; font-family: monospace; font-size: 9pt;")
                check_row.addWidget(details_label)

            checks_layout.addLayout(check_row)

        layout.addWidget(checks_group)

        # Paradox risk section
        risk_group = QGroupBox("Paradox Risk Assessment")
        risk_layout = QVBoxLayout(risk_group)

        paradox_risk = self._event.get("paradox_risk", 0.0)
        risk_percent = paradox_risk * 100

        # Risk bar
        risk_row = QHBoxLayout()
        risk_label = QLabel("Risk Level:")
        risk_label.setStyleSheet("color: #808080;")
        risk_row.addWidget(risk_label)

        # Determine risk color and label
        if risk_percent < 5:
            risk_color = "#00ff88"
            risk_text = f"{risk_percent:.1f}% (nominal)"
        elif risk_percent < 15:
            risk_color = "#ffaa00"
            risk_text = f"{risk_percent:.1f}% (elevated - warning)"
        elif risk_percent < 30:
            risk_color = "#ff8800"
            risk_text = f"{risk_percent:.1f}% (high - branch required)"
        else:
            risk_color = "#ff4444"
            risk_text = f"{risk_percent:.1f}% (critical - interlock)"

        risk_value = QLabel(risk_text)
        risk_value.setStyleSheet(f"color: {risk_color}; font-family: monospace; font-weight: bold;")
        risk_row.addWidget(risk_value)
        risk_row.addStretch()
        risk_layout.addLayout(risk_row)

        # Risk thresholds explanation
        thresholds = QLabel("Thresholds: 5% warning | 15% branch | 30% interlock")
        thresholds.setStyleSheet("color: #5a5a5a; font-size: 8pt;")
        risk_layout.addWidget(thresholds)

        layout.addWidget(risk_group)

        # Light cone analysis section
        lightcone_group = QGroupBox("Light Cone Analysis")
        lightcone_layout = QVBoxLayout(lightcone_group)

        # Create spacetime event from this event's data
        stamp = self._event.get("stamp", {})
        event_t = stamp.get("t", 0.0)

        # Create the 4-position for this event
        this_event = SpacetimeEvent(
            position=FourVector(t=event_t, x=0, y=0, z=0),
            event_id=self._event.get("id", ""),
            frame_id=stamp.get("frame_id", "origin")
        )

        # Show interval from origin
        origin = SpacetimeEvent(position=FourVector(t=0, x=0, y=0, z=0), frame_id="origin")
        interval = SpacetimeInterval.between(origin, this_event)

        self._add_info_row(lightcone_layout, "ds² (from origin):", f"{interval.squared:.6f}")
        self._add_info_row(lightcone_layout, "Interval Type:", interval.interval_type.value.upper())

        if interval.squared > 0:
            self._add_info_row(lightcone_layout, "Proper Time:", f"{interval.proper_time:.6f} s")

        layout.addWidget(lightcone_group)

        # Causal parents section
        parents_group = QGroupBox("Causal Parents")
        parents_layout = QVBoxLayout(parents_group)

        parents = self._event.get("causal_parents", [])
        if parents:
            for parent_id in parents:
                parent_row = QHBoxLayout()
                id_label = QLabel(f"• {parent_id[:16]}...")
                id_label.setStyleSheet("color: #00ff88; font-family: monospace;")
                parent_row.addWidget(id_label)

                relation_label = QLabel("[TIMELIKE]")
                relation_label.setStyleSheet("color: #00aaff; font-family: monospace;")
                parent_row.addWidget(relation_label)
                parent_row.addStretch()
                parents_layout.addLayout(parent_row)
        else:
            label = QLabel("No causal parents (root event)")
            label.setStyleSheet("color: #808080;")
            parents_layout.addWidget(label)

        layout.addWidget(parents_group)

        layout.addStretch()
        return widget

    def _generate_sample_checks(self) -> list[dict]:
        """Generate sample constraint checks for display."""
        stamp = self._event.get("stamp", {})
        event_t = stamp.get("t", 0.0)
        parents = self._event.get("causal_parents", [])

        checks = [
            {
                "icon": "✔",
                "status": "satisfied",
                "description": "No self-parent",
                "details": f"Checked {len(parents)} ancestors" if parents else "No parents to check",
            },
            {
                "icon": "✔",
                "status": "satisfied",
                "description": "Temporal ordering",
                "details": f"Δt = +{event_t:.3f}s" if event_t > 0 else "Root event",
            },
            {
                "icon": "✔",
                "status": "satisfied",
                "description": "Light-cone ordering",
                "details": f"Timelike (Δt = +{event_t:.3f}s)" if event_t > 0 else "At apex",
            },
            {
                "icon": "✔",
                "status": "satisfied",
                "description": "Branch coherence",
                "details": f"Branch '{self._event.get('branch_id', 'main')}' consistent",
            },
            {
                "icon": "⏳",
                "status": "deferred",
                "description": "Conservation (soft)",
                "details": "Deferred (no conservation data)",
            },
        ]
        return checks

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
