"""Constraint Visualization Widget - Interactive display of causality constraints."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from timeos.core.constraints import ConstraintCheck, ConstraintStatus


class ConstraintCard(QFrame):
    """Interactive card displaying a single constraint check."""

    clicked = Signal(object)  # Emits the ConstraintCheck

    # Status colors
    STATUS_COLORS = {
        ConstraintStatus.SATISFIED: "#00ff88",
        ConstraintStatus.WARNING: "#ffaa00",
        ConstraintStatus.VIOLATED: "#ff4444",
        ConstraintStatus.DEFERRED: "#808080",
    }

    # Status icons
    STATUS_ICONS = {
        ConstraintStatus.SATISFIED: "✔",
        ConstraintStatus.WARNING: "⚠",
        ConstraintStatus.VIOLATED: "✗",
        ConstraintStatus.DEFERRED: "⏳",
    }

    def __init__(self, check: ConstraintCheck, parent: QWidget | None = None):
        super().__init__(parent)

        self._check = check
        self._expanded = False

        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self) -> None:
        """Set up the card UI."""
        self.setFrameShape(QFrame.Shape.StyledPanel)

        color = self.STATUS_COLORS.get(self._check.status, "#808080")
        self.setStyleSheet(f"""
            ConstraintCard {{
                background-color: #1a1a1a;
                border: 1px solid {color};
                border-left: 4px solid {color};
                border-radius: 4px;
                padding: 8px;
            }}
            ConstraintCard:hover {{
                background-color: #252525;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Header row: icon + name + status
        header = QHBoxLayout()

        icon = self.STATUS_ICONS.get(self._check.status, "?")
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {color}; font-size: 14px;")
        header.addWidget(icon_label)

        name_label = QLabel(self._check.constraint_name)
        name_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        header.addWidget(name_label)

        header.addStretch()

        status_label = QLabel(self._check.status.value.upper())
        status_label.setStyleSheet(f"color: {color}; font-size: 10px;")
        header.addWidget(status_label)

        layout.addLayout(header)

        # Message row
        if self._check.message:
            msg_label = QLabel(self._check.message)
            msg_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
            msg_label.setWordWrap(True)
            layout.addWidget(msg_label)

        # Details row (metrics)
        if self._check.details:
            details_text = " | ".join(f"{k}: {v}" for k, v in self._check.details.items())
            details_label = QLabel(details_text)
            details_label.setStyleSheet("color: #606060; font-size: 10px; font-family: monospace;")
            layout.addWidget(details_label)

        # Expandable explanation
        self._explanation_label = QLabel()
        self._explanation_label.setStyleSheet("""
            color: #808080;
            font-size: 11px;
            background-color: #0d0d0d;
            padding: 8px;
            border-radius: 4px;
        """)
        self._explanation_label.setWordWrap(True)
        self._explanation_label.setVisible(False)
        layout.addWidget(self._explanation_label)

        # Set tooltip with full explanation
        self._set_tooltip()

    def _set_tooltip(self) -> None:
        """Set educational tooltip for this constraint."""
        explanations = {
            "No self-parent": (
                "<b>No Self-Causation Constraint</b><br><br>"
                "An event cannot be its own ancestor.<br><br>"
                "This prevents causal loops where an event<br>"
                "depends on itself through a chain of causality.<br><br>"
                "<b>Example violation:</b><br>"
                "A → B → C → A (loop detected)"
            ),
            "Causal ordering": (
                "<b>Causal Order Constraint</b><br><br>"
                "Parent events must occur BEFORE child events.<br><br>"
                "This is the fundamental arrow of time:<br>"
                "causes precede effects.<br><br>"
                "<b>Formula:</b> t_parent < t_child<br><br>"
                "<b>Violation:</b> Grandfather paradox"
            ),
            "Light-cone": (
                "<b>Light Cone Constraint</b><br><br>"
                "Events must be within each other's light cones<br>"
                "to be causally connected.<br><br>"
                "<b>Types of separation:</b><br>"
                "• Timelike: Can be causally connected<br>"
                "• Lightlike: Connected by light signal<br>"
                "• Spacelike: Causally disconnected<br><br>"
                "Nothing travels faster than light (c)."
            ),
            "Branch coherence": (
                "<b>Branch Coherence Constraint</b><br><br>"
                "Events in different branches cannot directly<br>"
                "reference each other without a merge.<br><br>"
                "Branches are isolated timelines that evolve<br>"
                "independently until explicitly merged."
            ),
            "Conservation": (
                "<b>Conservation Constraint (Soft)</b><br><br>"
                "Energy and momentum should be conserved.<br><br>"
                "This is a 'soft' constraint - violations<br>"
                "raise warnings but don't block operations.<br><br>"
                "Useful for detecting bootstrap paradoxes<br>"
                "where information appears from nowhere."
            ),
            "Information": (
                "<b>Information Conservation</b><br><br>"
                "Information must have an origin.<br><br>"
                "Bootstrap paradoxes violate this: a poem<br>"
                "exists in a loop with no external source.<br><br>"
                "Not a logical contradiction, but<br>"
                "thermodynamically suspicious."
            ),
        }

        # Find matching explanation
        for key, explanation in explanations.items():
            if key.lower() in self._check.constraint_name.lower():
                self.setToolTip(explanation)
                self._explanation_label.setText(explanation.replace("<br>", "\n").replace("<b>", "").replace("</b>", ""))
                return

        # Default tooltip
        self.setToolTip(f"<b>{self._check.constraint_name}</b><br><br>{self._check.message or 'No details available.'}")

    def mousePressEvent(self, event) -> None:
        """Handle click to toggle expansion."""
        self._expanded = not self._expanded
        self._explanation_label.setVisible(self._expanded)
        self.clicked.emit(self._check)
        super().mousePressEvent(event)

    def get_check(self) -> ConstraintCheck:
        """Get the constraint check."""
        return self._check


class RiskGauge(QWidget):
    """Visual gauge showing paradox risk level."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._risk = 0.0
        self.setMinimumSize(200, 60)
        self.setMaximumHeight(80)

    def set_risk(self, risk: float) -> None:
        """Set the risk level (0.0 to 1.0)."""
        self._risk = max(0.0, min(1.0, risk))
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the risk gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#0d0d0d"))

        # Gauge track
        track_y = 30
        track_h = 16
        track_margin = 10

        # Draw threshold zones
        zones = [
            (0.0, 0.05, "#00ff88", "Nominal"),
            (0.05, 0.15, "#ffff00", "Warning"),
            (0.15, 0.30, "#ff8800", "Branch"),
            (0.30, 1.0, "#ff4444", "Interlock"),
        ]

        for start, end, color, label in zones:
            x1 = track_margin + int(start * (w - 2 * track_margin))
            x2 = track_margin + int(end * (w - 2 * track_margin))
            painter.fillRect(x1, track_y, x2 - x1, track_h, QColor(color).darker(200))

        # Draw current risk indicator
        risk_x = track_margin + int(self._risk * (w - 2 * track_margin))

        # Determine color based on risk
        if self._risk < 0.05:
            color = QColor("#00ff88")
            status = "NOMINAL"
        elif self._risk < 0.15:
            color = QColor("#ffff00")
            status = "WARNING"
        elif self._risk < 0.30:
            color = QColor("#ff8800")
            status = "BRANCH"
        else:
            color = QColor("#ff4444")
            status = "INTERLOCK"

        # Draw filled portion
        painter.fillRect(track_margin, track_y, risk_x - track_margin, track_h, color)

        # Draw indicator line
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawLine(risk_x, track_y - 5, risk_x, track_y + track_h + 5)

        # Draw text
        painter.setFont(QFont("monospace", 10))

        # Risk percentage
        painter.setPen(color)
        risk_text = f"{self._risk * 100:.1f}%"
        painter.drawText(10, 20, risk_text)

        # Status
        painter.drawText(w - 80, 20, status)

        # Threshold markers
        painter.setPen(QColor("#606060"))
        painter.setFont(QFont("monospace", 8))
        for threshold, label in [(0.05, "5%"), (0.15, "15%"), (0.30, "30%")]:
            tx = track_margin + int(threshold * (w - 2 * track_margin))
            painter.drawLine(tx, track_y + track_h, tx, track_y + track_h + 3)
            painter.drawText(tx - 10, track_y + track_h + 14, label)

        painter.end()


class ConstraintView(QWidget):
    """Widget displaying all constraint checks for an event."""

    constraint_clicked = Signal(object)  # Emits ConstraintCheck

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._checks: list[ConstraintCheck] = []
        self._risk = 0.0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Risk gauge
        self._risk_gauge = RiskGauge()
        layout.addWidget(self._risk_gauge)

        # Risk explanation
        self._risk_label = QLabel()
        self._risk_label.setStyleSheet("color: #808080; font-size: 10px;")
        self._risk_label.setWordWrap(True)
        layout.addWidget(self._risk_label)

        # Scroll area for constraint cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()

        scroll.setWidget(self._cards_container)
        layout.addWidget(scroll)

    def set_checks(self, checks: list[ConstraintCheck], risk: float = 0.0) -> None:
        """Set the constraint checks to display."""
        self._checks = checks
        self._risk = risk

        # Update risk gauge
        self._risk_gauge.set_risk(risk)

        # Update risk explanation
        self._update_risk_explanation()

        # Clear existing cards
        while self._cards_layout.count() > 1:  # Keep the stretch
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new cards
        for check in checks:
            card = ConstraintCard(check)
            card.clicked.connect(self._on_card_clicked)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _update_risk_explanation(self) -> None:
        """Update the risk explanation text."""
        if self._risk < 0.05:
            text = "All constraints satisfied. Timeline is consistent."
        elif self._risk < 0.15:
            text = "Minor concerns detected. Proceed with caution."
        elif self._risk < 0.30:
            text = "Elevated risk. Operation will be isolated to a branch."
        else:
            text = "Critical risk! Safety interlock would block this operation."

        # Count by status
        satisfied = sum(1 for c in self._checks if c.status == ConstraintStatus.SATISFIED)
        warnings = sum(1 for c in self._checks if c.status == ConstraintStatus.WARNING)
        violated = sum(1 for c in self._checks if c.status == ConstraintStatus.VIOLATED)
        deferred = sum(1 for c in self._checks if c.status == ConstraintStatus.DEFERRED)

        stats = f"✔ {satisfied}  ⚠ {warnings}  ✗ {violated}  ⏳ {deferred}"
        self._risk_label.setText(f"{text}\n{stats}")

    def _on_card_clicked(self, check: ConstraintCheck) -> None:
        """Handle constraint card click."""
        self.constraint_clicked.emit(check)

    def get_risk(self) -> float:
        """Get the current risk level."""
        return self._risk
