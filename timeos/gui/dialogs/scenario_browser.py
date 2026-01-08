"""Scenario Browser Dialog - Browse and load demo scenarios."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QSplitter,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal

from timeos.paradoxes import (
    Scenario,
    ScenarioCategory,
    list_scenarios,
    get_scenario,
    SCENARIOS_BY_CATEGORY,
)


class ScenarioBrowserDialog(QDialog):
    """Dialog for browsing and selecting demo scenarios."""

    scenario_selected = Signal(str)  # Emits scenario name

    def __init__(self, parent=None):
        super().__init__(parent)

        self._selected_scenario: Scenario | None = None

        self._setup_ui()
        self._connect_signals()
        self._populate_categories()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Load Demo Scenario")
        self.setMinimumSize(700, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel("Select a demo scenario to explore TimeOS features:")
        header.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addWidget(header)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: category and scenario list
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right: scenario details
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([250, 450])
        layout.addWidget(splitter)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._load_btn = QPushButton("Load Scenario")
        self._load_btn.setProperty("primary", True)
        self._load_btn.setMinimumSize(120, 32)
        self._load_btn.setEnabled(False)
        button_layout.addWidget(self._load_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setMinimumSize(80, 32)
        button_layout.addWidget(self._cancel_btn)

        layout.addLayout(button_layout)

    def _create_left_panel(self) -> QGroupBox:
        """Create the left panel with category filter and scenario list."""
        group = QGroupBox("Scenarios")
        layout = QVBoxLayout(group)

        # Category filter
        cat_layout = QHBoxLayout()
        cat_label = QLabel("Category:")
        cat_label.setStyleSheet("color: #808080;")
        cat_layout.addWidget(cat_label)

        self._category_combo = QComboBox()
        self._category_combo.addItem("All Categories", None)
        for cat in ScenarioCategory:
            self._category_combo.addItem(cat.value.title(), cat)
        cat_layout.addWidget(self._category_combo)
        cat_layout.addStretch()
        layout.addLayout(cat_layout)

        # Scenario list
        self._scenario_list = QListWidget()
        self._scenario_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
            }
            QListWidget::item {
                padding: 6px;
            }
            QListWidget::item:selected {
                background-color: #2d5016;
            }
        """)
        layout.addWidget(self._scenario_list)

        return group

    def _create_right_panel(self) -> QGroupBox:
        """Create the right panel with scenario details."""
        group = QGroupBox("Details")
        layout = QVBoxLayout(group)

        self._details_edit = QTextEdit()
        self._details_edit.setReadOnly(True)
        self._details_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d0d;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                font-family: monospace;
            }
        """)
        self._details_edit.setPlaceholderText("Select a scenario to view details...")
        layout.addWidget(self._details_edit)

        return group

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._category_combo.currentIndexChanged.connect(self._on_category_changed)
        self._scenario_list.currentItemChanged.connect(self._on_scenario_selected)
        self._scenario_list.itemDoubleClicked.connect(self._on_load)
        self._load_btn.clicked.connect(self._on_load)
        self._cancel_btn.clicked.connect(self.reject)

    def _populate_categories(self) -> None:
        """Populate the scenario list."""
        self._populate_scenario_list(None)

    def _populate_scenario_list(self, category: ScenarioCategory | None) -> None:
        """Populate scenario list for given category."""
        self._scenario_list.clear()

        scenarios = list_scenarios(category)

        for scenario in scenarios:
            item = QListWidgetItem()

            # Format: category tag + name
            cat_tag = f"[{scenario.category.value[:4].upper()}]"
            risk_str = f" ({scenario.expected_risk*100:.0f}%)" if scenario.expected_risk else ""

            item.setText(f"{cat_tag} {scenario.title}{risk_str}")
            item.setData(Qt.ItemDataRole.UserRole, scenario.name)

            # Color-code by risk level
            if scenario.expected_risk >= 0.30:
                item.setForeground(Qt.GlobalColor.red)
            elif scenario.expected_risk >= 0.15:
                item.setForeground(Qt.GlobalColor.darkYellow)
            elif scenario.expected_risk >= 0.05:
                item.setForeground(Qt.GlobalColor.yellow)

            self._scenario_list.addItem(item)

    def _on_category_changed(self, index: int) -> None:
        """Handle category filter change."""
        category = self._category_combo.currentData()
        self._populate_scenario_list(category)
        self._selected_scenario = None
        self._load_btn.setEnabled(False)
        self._details_edit.clear()

    def _on_scenario_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        """Handle scenario selection."""
        if not current:
            self._selected_scenario = None
            self._load_btn.setEnabled(False)
            self._details_edit.clear()
            return

        name = current.data(Qt.ItemDataRole.UserRole)
        scenario = get_scenario(name)

        if not scenario:
            return

        self._selected_scenario = scenario
        self._load_btn.setEnabled(True)
        self._update_details(scenario)

    def _update_details(self, scenario: Scenario) -> None:
        """Update the details panel."""
        lines = []

        # Title and category
        lines.append(f"<h3 style='color: #00ff88;'>{scenario.title}</h3>")
        lines.append(f"<p style='color: #808080;'>Category: {scenario.category.value}</p>")

        # Description
        lines.append(f"<p>{scenario.description}</p>")

        # Learning objectives
        if scenario.learning_objectives:
            lines.append("<p><b style='color: #88ccff;'>Learning Objectives:</b></p>")
            lines.append("<ul>")
            for obj in scenario.learning_objectives:
                lines.append(f"<li>{obj}</li>")
            lines.append("</ul>")

        # Events
        lines.append(f"<p><b style='color: #88ccff;'>Events ({len(scenario.events)}):</b></p>")
        lines.append("<pre style='color: #a0a0a0; margin-left: 10px;'>")
        for event in scenario.events:
            parent_str = f" <- {', '.join(event.parent_names)}" if event.parent_names else ""
            branch_str = f" [{event.branch_id}]" if event.branch_id != "main" else ""
            lines.append(f"  t={event.t:>5.1f}: {event.name}{branch_str}{parent_str}")
        lines.append("</pre>")

        # Branches
        if scenario.branches:
            lines.append(f"<p><b style='color: #88ccff;'>Branches:</b> {', '.join(scenario.branches)}</p>")

        # Risk
        if scenario.expected_risk:
            risk_color = self._risk_color(scenario.expected_risk)
            lines.append(f"<p><b style='color: #88ccff;'>Expected Paradox Risk:</b> "
                        f"<span style='color: {risk_color};'>{scenario.expected_risk*100:.0f}%</span></p>")

        self._details_edit.setHtml("".join(lines))

    def _risk_color(self, risk: float) -> str:
        """Get color for risk level."""
        if risk >= 0.30:
            return "#ff4444"
        elif risk >= 0.15:
            return "#ff8800"
        elif risk >= 0.05:
            return "#ffff00"
        return "#00ff88"

    def _on_load(self) -> None:
        """Handle load button click."""
        if self._selected_scenario:
            self.scenario_selected.emit(self._selected_scenario.name)
            self.accept()

    def get_selected_scenario(self) -> Scenario | None:
        """Get the selected scenario."""
        return self._selected_scenario
