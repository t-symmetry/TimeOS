"""Failure Injection Dialog - Inject failures into emulated hardware for testing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QWidget,
    QFormLayout,
    QTextEdit,
    QSplitter,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal


class FailureType(Enum):
    """Types of failures that can be injected."""
    SENSOR_DRIFT = "sensor_drift"
    SENSOR_NOISE = "sensor_noise"
    SENSOR_STUCK = "sensor_stuck"
    COMMUNICATION_TIMEOUT = "comm_timeout"
    COMMUNICATION_CORRUPT = "comm_corrupt"
    POWER_SUPPLY_RIPPLE = "power_ripple"
    POWER_SUPPLY_SAG = "power_sag"
    THERMAL_RUNAWAY = "thermal_runaway"
    QUENCH = "quench"
    INTERLOCK_TRIP = "interlock_trip"
    CALIBRATION_DRIFT = "calibration_drift"


@dataclass
class FailureScenario:
    """A predefined failure scenario."""
    name: str
    description: str
    failure_type: FailureType
    target_module: str
    severity: float  # 0.0 to 1.0
    duration: float  # seconds, 0 = permanent
    parameters: dict


# Predefined failure scenarios
FAILURE_SCENARIOS = [
    FailureScenario(
        name="Sensor Drift - Minor",
        description="Gradual drift in field sensor readings. Simulates calibration degradation.",
        failure_type=FailureType.SENSOR_DRIFT,
        target_module="field_generator",
        severity=0.2,
        duration=60.0,
        parameters={"drift_rate": 0.001, "max_drift": 0.05},
    ),
    FailureScenario(
        name="Sensor Drift - Major",
        description="Significant sensor drift requiring recalibration.",
        failure_type=FailureType.SENSOR_DRIFT,
        target_module="field_generator",
        severity=0.6,
        duration=0,  # permanent
        parameters={"drift_rate": 0.01, "max_drift": 0.2},
    ),
    FailureScenario(
        name="Noisy Sensors",
        description="Increased noise on all sensor readings.",
        failure_type=FailureType.SENSOR_NOISE,
        target_module="field_generator",
        severity=0.4,
        duration=30.0,
        parameters={"noise_amplitude": 0.05, "noise_frequency": 50.0},
    ),
    FailureScenario(
        name="Stuck Sensor",
        description="Temperature sensor stuck at last reading.",
        failure_type=FailureType.SENSOR_STUCK,
        target_module="thermal",
        severity=0.7,
        duration=0,
        parameters={"stuck_value": 4.2},
    ),
    FailureScenario(
        name="Communication Timeout",
        description="Intermittent communication failures with module.",
        failure_type=FailureType.COMMUNICATION_TIMEOUT,
        target_module="tdu",
        severity=0.5,
        duration=20.0,
        parameters={"timeout_probability": 0.3, "timeout_duration": 2.0},
    ),
    FailureScenario(
        name="Data Corruption",
        description="Corrupted data packets from sensor network.",
        failure_type=FailureType.COMMUNICATION_CORRUPT,
        target_module="causality_monitor",
        severity=0.6,
        duration=15.0,
        parameters={"corruption_rate": 0.1, "bit_flip_count": 2},
    ),
    FailureScenario(
        name="Power Supply Ripple",
        description="Increased ripple on power supply output.",
        failure_type=FailureType.POWER_SUPPLY_RIPPLE,
        target_module="field_generator",
        severity=0.3,
        duration=45.0,
        parameters={"ripple_amplitude": 0.02, "ripple_frequency": 120.0},
    ),
    FailureScenario(
        name="Power Sag",
        description="Voltage sag under load conditions.",
        failure_type=FailureType.POWER_SUPPLY_SAG,
        target_module="field_generator",
        severity=0.5,
        duration=10.0,
        parameters={"sag_percentage": 0.15, "recovery_time": 5.0},
    ),
    FailureScenario(
        name="Thermal Excursion",
        description="Unexpected temperature rise in cryostat.",
        failure_type=FailureType.THERMAL_RUNAWAY,
        target_module="thermal",
        severity=0.7,
        duration=30.0,
        parameters={"heat_rate": 0.5, "max_temp": 8.0},
    ),
    FailureScenario(
        name="Quench Event",
        description="Simulated superconducting magnet quench.",
        failure_type=FailureType.QUENCH,
        target_module="field_generator",
        severity=1.0,
        duration=0,  # permanent until reset
        parameters={"quench_propagation": 0.1, "energy_dump_time": 2.0},
    ),
    FailureScenario(
        name="Spurious Interlock",
        description="False interlock trip - no actual fault.",
        failure_type=FailureType.INTERLOCK_TRIP,
        target_module="safety",
        severity=0.4,
        duration=0,
        parameters={"interlock_id": "temp_high", "actual_fault": False},
    ),
    FailureScenario(
        name="Calibration Error",
        description="Incorrect calibration coefficients loaded.",
        failure_type=FailureType.CALIBRATION_DRIFT,
        target_module="field_generator",
        severity=0.5,
        duration=0,
        parameters={"scale_error": 1.05, "offset_error": 0.02},
    ),
]


class FailureInjectionDialog(QDialog):
    """Dialog for injecting failures into emulated hardware.

    Allows testing of:
    - Sensor failures and degradation
    - Communication issues
    - Power supply problems
    - Thermal events
    - Safety system testing
    """

    # Signals
    failure_injected = Signal(str, dict)  # scenario_name, parameters
    failure_cleared = Signal(str)  # scenario_name
    all_failures_cleared = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setWindowTitle("Failure Injection")
        self.setMinimumSize(700, 500)

        self._active_failures: dict[str, FailureScenario] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Splitter for scenario list and details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Scenario list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        scenarios_group = QGroupBox("Available Scenarios")
        scenarios_layout = QVBoxLayout(scenarios_group)

        self._scenarios_table = QTableWidget()
        self._scenarios_table.setColumnCount(4)
        self._scenarios_table.setHorizontalHeaderLabels([
            "Scenario", "Module", "Severity", "Status"
        ])
        self._scenarios_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._scenarios_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._scenarios_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._scenarios_table.itemSelectionChanged.connect(
            self._on_scenario_selected
        )

        self._populate_scenarios_table()
        scenarios_layout.addWidget(self._scenarios_table)

        left_layout.addWidget(scenarios_group)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))

        self._module_filter = QComboBox()
        self._module_filter.addItems([
            "All Modules",
            "field_generator",
            "tdu",
            "thermal",
            "causality_monitor",
            "safety",
        ])
        self._module_filter.currentTextChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._module_filter)

        left_layout.addLayout(filter_layout)

        splitter.addWidget(left_widget)

        # Right: Details and controls
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Scenario details
        details_group = QGroupBox("Scenario Details")
        details_layout = QVBoxLayout(details_group)

        self._scenario_name_label = QLabel("Select a scenario")
        self._scenario_name_label.setStyleSheet(
            "font-weight: bold; font-size: 14px;"
        )
        details_layout.addWidget(self._scenario_name_label)

        self._scenario_desc_text = QTextEdit()
        self._scenario_desc_text.setReadOnly(True)
        self._scenario_desc_text.setMaximumHeight(80)
        details_layout.addWidget(self._scenario_desc_text)

        # Parameters
        params_layout = QFormLayout()

        self._severity_spin = QDoubleSpinBox()
        self._severity_spin.setRange(0.0, 1.0)
        self._severity_spin.setSingleStep(0.1)
        self._severity_spin.setValue(0.5)
        params_layout.addRow("Severity:", self._severity_spin)

        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.0, 3600.0)
        self._duration_spin.setSingleStep(10.0)
        self._duration_spin.setValue(30.0)
        self._duration_spin.setSuffix(" s")
        self._duration_spin.setSpecialValueText("Permanent")
        params_layout.addRow("Duration:", self._duration_spin)

        details_layout.addLayout(params_layout)

        right_layout.addWidget(details_group)

        # Injection controls
        inject_group = QGroupBox("Injection Controls")
        inject_layout = QVBoxLayout(inject_group)

        btn_row1 = QHBoxLayout()

        self._inject_btn = QPushButton("Inject Failure")
        self._inject_btn.setStyleSheet(
            "QPushButton { background-color: #5a2d2d; }"
            "QPushButton:hover { background-color: #7a3d3d; }"
        )
        self._inject_btn.clicked.connect(self._on_inject)
        btn_row1.addWidget(self._inject_btn)

        self._clear_selected_btn = QPushButton("Clear Selected")
        self._clear_selected_btn.clicked.connect(self._on_clear_selected)
        btn_row1.addWidget(self._clear_selected_btn)

        inject_layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()

        self._clear_all_btn = QPushButton("Clear All Failures")
        self._clear_all_btn.clicked.connect(self._on_clear_all)
        btn_row2.addWidget(self._clear_all_btn)

        inject_layout.addLayout(btn_row2)

        right_layout.addWidget(inject_group)

        # Active failures
        active_group = QGroupBox("Active Failures")
        active_layout = QVBoxLayout(active_group)

        self._active_table = QTableWidget()
        self._active_table.setColumnCount(4)
        self._active_table.setHorizontalHeaderLabels([
            "Scenario", "Severity", "Remaining", "Action"
        ])
        self._active_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        active_layout.addWidget(self._active_table)

        right_layout.addWidget(active_group)

        splitter.addWidget(right_widget)

        # Set splitter proportions
        splitter.setSizes([350, 350])

        layout.addWidget(splitter)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._close_btn)

        layout.addLayout(btn_layout)

    def _populate_scenarios_table(self) -> None:
        """Populate the scenarios table."""
        self._scenarios_table.setRowCount(len(FAILURE_SCENARIOS))

        for row, scenario in enumerate(FAILURE_SCENARIOS):
            # Name
            name_item = QTableWidgetItem(scenario.name)
            name_item.setData(Qt.ItemDataRole.UserRole, row)
            self._scenarios_table.setItem(row, 0, name_item)

            # Module
            self._scenarios_table.setItem(
                row, 1, QTableWidgetItem(scenario.target_module)
            )

            # Severity
            severity_item = QTableWidgetItem(f"{scenario.severity:.0%}")
            if scenario.severity >= 0.7:
                severity_item.setForeground(Qt.GlobalColor.red)
            elif scenario.severity >= 0.4:
                severity_item.setForeground(Qt.GlobalColor.yellow)
            else:
                severity_item.setForeground(Qt.GlobalColor.green)
            self._scenarios_table.setItem(row, 2, severity_item)

            # Status
            status = "Active" if scenario.name in self._active_failures else "Ready"
            status_item = QTableWidgetItem(status)
            if status == "Active":
                status_item.setForeground(Qt.GlobalColor.red)
            self._scenarios_table.setItem(row, 3, status_item)

    def _apply_filter(self, filter_text: str) -> None:
        """Apply module filter to scenarios table."""
        for row in range(self._scenarios_table.rowCount()):
            module_item = self._scenarios_table.item(row, 1)
            if module_item:
                if filter_text == "All Modules":
                    self._scenarios_table.setRowHidden(row, False)
                else:
                    self._scenarios_table.setRowHidden(
                        row, module_item.text() != filter_text
                    )

    def _on_scenario_selected(self) -> None:
        """Handle scenario selection."""
        selected = self._scenarios_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        scenario = FAILURE_SCENARIOS[row]

        self._scenario_name_label.setText(scenario.name)
        self._scenario_desc_text.setPlainText(scenario.description)
        self._severity_spin.setValue(scenario.severity)
        self._duration_spin.setValue(scenario.duration)

    def _on_inject(self) -> None:
        """Inject the selected failure."""
        selected = self._scenarios_table.selectedItems()
        if not selected:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select a failure scenario to inject.",
            )
            return

        row = selected[0].row()
        scenario = FAILURE_SCENARIOS[row]

        # Create modified scenario with current parameters
        modified_params = {
            **scenario.parameters,
            "severity": self._severity_spin.value(),
            "duration": self._duration_spin.value(),
        }

        # Add to active failures
        self._active_failures[scenario.name] = scenario
        self._update_active_table()
        self._update_scenario_status(row, "Active")

        # Emit signal
        self.failure_injected.emit(scenario.name, modified_params)

        QMessageBox.information(
            self,
            "Failure Injected",
            f"Injected failure: {scenario.name}\n"
            f"Target: {scenario.target_module}\n"
            f"Severity: {self._severity_spin.value():.0%}\n"
            f"Duration: {self._duration_spin.value():.1f}s"
            if self._duration_spin.value() > 0
            else f"Duration: Permanent",
        )

    def _on_clear_selected(self) -> None:
        """Clear the selected failure."""
        selected = self._scenarios_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        scenario = FAILURE_SCENARIOS[row]

        if scenario.name in self._active_failures:
            del self._active_failures[scenario.name]
            self._update_active_table()
            self._update_scenario_status(row, "Ready")
            self.failure_cleared.emit(scenario.name)

    def _on_clear_all(self) -> None:
        """Clear all active failures."""
        if not self._active_failures:
            return

        result = QMessageBox.question(
            self,
            "Clear All Failures",
            f"Clear all {len(self._active_failures)} active failures?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if result == QMessageBox.StandardButton.Yes:
            self._active_failures.clear()
            self._update_active_table()
            self._populate_scenarios_table()  # Reset all statuses
            self.all_failures_cleared.emit()

    def _update_scenario_status(self, row: int, status: str) -> None:
        """Update the status of a scenario in the table."""
        status_item = self._scenarios_table.item(row, 3)
        if status_item:
            status_item.setText(status)
            if status == "Active":
                status_item.setForeground(Qt.GlobalColor.red)
            else:
                status_item.setForeground(Qt.GlobalColor.white)

    def _update_active_table(self) -> None:
        """Update the active failures table."""
        self._active_table.setRowCount(len(self._active_failures))

        for row, (name, scenario) in enumerate(self._active_failures.items()):
            # Name
            self._active_table.setItem(row, 0, QTableWidgetItem(name))

            # Severity
            self._active_table.setItem(
                row, 1, QTableWidgetItem(f"{scenario.severity:.0%}")
            )

            # Remaining time
            if scenario.duration > 0:
                self._active_table.setItem(
                    row, 2, QTableWidgetItem(f"{scenario.duration:.0f}s")
                )
            else:
                self._active_table.setItem(row, 2, QTableWidgetItem("Permanent"))

            # Clear button
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(
                lambda checked, n=name: self._clear_failure(n)
            )
            self._active_table.setCellWidget(row, 3, clear_btn)

    def _clear_failure(self, name: str) -> None:
        """Clear a specific failure by name."""
        if name in self._active_failures:
            del self._active_failures[name]
            self._update_active_table()
            self._populate_scenarios_table()
            self.failure_cleared.emit(name)

    def get_active_failures(self) -> dict[str, FailureScenario]:
        """Get currently active failures."""
        return self._active_failures.copy()
