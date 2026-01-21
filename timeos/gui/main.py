"""TimeOS GUI Main Window - Mission Control Interface."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QFrame,
    QMenuBar,
    QMenu,
    QStatusBar,
    QLabel,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QSettings, QByteArray
from PySide6.QtGui import QAction, QKeySequence

from timeos.gui.widgets.status_panel import StatusPanel
from timeos.gui.widgets.position_display import PositionDisplay
from timeos.gui.widgets.simultaneity_widget import SimultaneityWidget
from timeos.gui.widgets.field_monitor import FieldMonitor
from timeos.gui.widgets.timeline_view import TimelineView
from timeos.gui.widgets.event_log import EventLogWidget
from timeos.gui.widgets.control_panel import ControlPanel
from timeos.gui.widgets.thermal_panel import ThermalPanel
from timeos.gui.widgets.data_logger_panel import DataLoggerPanel
from timeos.gui.widgets.clock_status_panel import ClockStatusPanel
from timeos.gui.models.machine_model import MachineModel


class MainWindow(QMainWindow):
    """Main window for TimeOS Control application."""

    def __init__(
        self,
        demo: bool = False,
        emulated: bool = False,
        ros2: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self._demo = demo
        self._emulated = emulated
        self._ros2 = ros2

        # Choose model based on mode
        if ros2:
            from timeos.gui.models.ros2_machine_model import ROS2MachineModel
            self._model = ROS2MachineModel()
        else:
            self._model = MachineModel(demo=demo, emulated=emulated)

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._connect_signals()
        self._start_update_timer()
        self._restore_settings()

        # Initialize the machine
        self._model.initialize()

    def _setup_ui(self) -> None:
        """Set up the main window UI layout."""
        # Build title with mode indicators
        title = "TimeOS Control"
        modes = []
        if self._ros2:
            modes.append("ROS2")
        if self._emulated:
            modes.append("Emulated")
        if self._demo:
            modes.append("Demo")
        if modes:
            title += f" [{' + '.join(modes)}]"

        self.setWindowTitle(title)
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main layout
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Left panel (status widgets)
        left_panel = self._create_left_panel()

        # Right panel (main content)
        right_panel = self._create_right_panel()

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 900])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _create_left_panel(self) -> QWidget:
        """Create the left status panel."""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(250)
        panel.setMaximumWidth(350)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Status panel
        self._status_panel = StatusPanel(self._model)
        layout.addWidget(self._status_panel)

        # Position display
        self._position_display = PositionDisplay(self._model)
        layout.addWidget(self._position_display)

        # Simultaneity offset display (Andromeda Paradox)
        self._simultaneity_widget = SimultaneityWidget(self._model)
        layout.addWidget(self._simultaneity_widget)

        # Field monitor
        self._field_monitor = FieldMonitor(self._model)
        layout.addWidget(self._field_monitor)

        # Clock status panel
        self._clock_panel = ClockStatusPanel()
        layout.addWidget(self._clock_panel)

        # Thermal panel (only in emulated mode)
        if self._emulated:
            self._thermal_panel = ThermalPanel()
            layout.addWidget(self._thermal_panel)
        else:
            self._thermal_panel = None

        layout.addStretch()

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create the right main content panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Top section: Timeline visualization
        self._timeline_view = TimelineView(self._model)
        self._timeline_view.setMinimumHeight(200)

        # Middle section: Event log
        self._event_log = EventLogWidget(self._model)

        # Bottom section: Control panel
        self._control_panel = ControlPanel(self._model)

        # Vertical splitter for right panel
        vsplitter = QSplitter(Qt.Orientation.Vertical)
        vsplitter.addWidget(self._timeline_view)
        vsplitter.addWidget(self._event_log)
        vsplitter.addWidget(self._control_panel)
        vsplitter.setSizes([250, 200, 150])

        layout.addWidget(vsplitter)

        return panel

    def _setup_menu(self) -> None:
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Session", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_session)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        # Scenarios submenu
        scenarios_menu = file_menu.addMenu("&Load Scenario")

        browse_scenarios_action = QAction("&Browse Scenarios...", self)
        browse_scenarios_action.setShortcut(QKeySequence("Ctrl+L"))
        browse_scenarios_action.triggered.connect(self._on_browse_scenarios)
        scenarios_menu.addAction(browse_scenarios_action)

        scenarios_menu.addSeparator()

        # Quick access to common scenarios
        quick_scenarios = [
            ("simple_timeline", "Simple Timeline"),
            ("branching", "Timeline Branching"),
            ("causal_chain", "Causal Chain"),
            ("low_risk", "Low Risk Demo"),
        ]
        for name, title in quick_scenarios:
            action = QAction(title, self)
            action.setData(name)
            action.triggered.connect(lambda checked, n=name: self._on_quick_scenario(n))
            scenarios_menu.addAction(action)

        file_menu.addSeparator()

        export_action = QAction("&Export Log...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._on_export_log)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Operations menu
        ops_menu = menubar.addMenu("&Operations")

        displace_action = QAction("&Displace...", self)
        displace_action.setShortcut(QKeySequence("Ctrl+D"))
        displace_action.triggered.connect(self._on_displace)
        ops_menu.addAction(displace_action)

        return_action = QAction("&Return to Anchor", self)
        return_action.setShortcut(QKeySequence("Ctrl+R"))
        return_action.triggered.connect(self._on_return)
        ops_menu.addAction(return_action)

        ops_menu.addSeparator()

        estop_action = QAction("&Emergency Stop", self)
        estop_action.setShortcut(QKeySequence("Ctrl+Shift+X"))
        estop_action.triggered.connect(self._on_emergency_stop)
        ops_menu.addAction(estop_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        reset_layout_action = QAction("&Reset Layout", self)
        reset_layout_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_layout_action.triggered.connect(self._on_reset_layout)
        view_menu.addAction(reset_layout_action)

        refresh_action = QAction("Re&fresh", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._on_refresh)
        view_menu.addAction(refresh_action)

        view_menu.addSeparator()

        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.setCheckable(True)
        fullscreen_action.triggered.connect(self._on_toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        self._fullscreen_action = fullscreen_action

        # Hardware menu
        hardware_menu = menubar.addMenu("&Hardware")
        self._hardware_menu = hardware_menu

        # Mode indicator and switch
        mode_str = []
        if self._ros2:
            mode_str.append("ROS2")
        if self._emulated:
            mode_str.append("Emulated")
        if self._demo:
            mode_str.append("Demo")
        if not mode_str:
            mode_str.append("Normal")

        switch_mode_action = QAction(f"Mode: {' + '.join(mode_str)}  (click to switch)", self)
        switch_mode_action.triggered.connect(self._on_switch_mode)
        hardware_menu.addAction(switch_mode_action)

        hardware_menu.addSeparator()

        # Module enable/disable checkboxes
        self._module_actions = {}
        module_names = {
            "field_generator": "Field Generator",
            "tdu": "Temporal Displacement Unit",
            "causality": "Causality Monitor",
            "safety": "Safety Interlocks",
            "thermal": "Thermal System",
        }
        for module_id, display_name in module_names.items():
            action = QAction(display_name, self)
            action.setCheckable(True)
            action.setChecked(self._model.get_module_enabled(module_id))
            action.setData(module_id)
            action.triggered.connect(
                lambda checked, m=module_id: self._on_toggle_module(m, checked)
            )
            hardware_menu.addAction(action)
            self._module_actions[module_id] = action

        hardware_menu.addSeparator()

        # Hardware status
        hw_status_action = QAction("Show Hardware Status...", self)
        hw_status_action.triggered.connect(self._on_show_hw_status)
        hardware_menu.addAction(hw_status_action)

        hardware_menu.addSeparator()

        # HIL Configuration
        hil_config_action = QAction("HIL Configuration...", self)
        hil_config_action.triggered.connect(self._on_hil_config)
        hardware_menu.addAction(hil_config_action)

        # Failure Injection
        failure_action = QAction("Failure Injection...", self)
        failure_action.triggered.connect(self._on_failure_injection)
        failure_action.setEnabled(self._emulated)  # Only in emulated mode
        hardware_menu.addAction(failure_action)

        # Data Logger
        data_logger_action = QAction("Data Logger...", self)
        data_logger_action.triggered.connect(self._on_data_logger)
        hardware_menu.addAction(data_logger_action)

        hardware_menu.addSeparator()

        # ROS2 Management
        ros2_action = QAction("ROS2 Management...", self)
        ros2_action.triggered.connect(self._on_ros2_management)
        hardware_menu.addAction(ros2_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        correlation_action = QAction("Stream &Correlation...", self)
        correlation_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        correlation_action.triggered.connect(self._on_correlation)
        tools_menu.addAction(correlation_action)

        drift_action = QAction("&Drift Monitor...", self)
        drift_action.triggered.connect(self._on_drift_monitor)
        tools_menu.addAction(drift_action)

        tools_menu.addSeparator()

        # Export submenu
        export_menu = tools_menu.addMenu("&Export Timeline")

        export_json_action = QAction("JSON...", self)
        export_json_action.triggered.connect(lambda: self._on_export_format("json"))
        export_menu.addAction(export_json_action)

        export_csv_action = QAction("CSV...", self)
        export_csv_action.triggered.connect(lambda: self._on_export_format("csv"))
        export_menu.addAction(export_csv_action)

        export_prov_action = QAction("W3C PROV (Turtle)...", self)
        export_prov_action.triggered.connect(lambda: self._on_export_format("prov"))
        export_menu.addAction(export_prov_action)

        export_influx_action = QAction("InfluxDB Line Protocol...", self)
        export_influx_action.triggered.connect(lambda: self._on_export_format("influx"))
        export_menu.addAction(export_influx_action)

        # Learn menu
        learn_menu = menubar.addMenu("&Learn")

        walkthrough_action = QAction("&Walkthroughs...", self)
        walkthrough_action.setShortcut(QKeySequence("Ctrl+W"))
        walkthrough_action.triggered.connect(self._on_open_walkthrough)
        learn_menu.addAction(walkthrough_action)

        learn_menu.addSeparator()

        # Quick walkthrough access
        quick_walkthroughs = [
            ("simple_timeline", "Your First Timeline"),
            ("branching", "Exploring Alternatives"),
            ("grandfather_paradox", "The Grandfather Paradox"),
            ("risk_escalation", "Understanding Risk Levels"),
        ]
        for name, title in quick_walkthroughs:
            action = QAction(title, self)
            action.setData(name)
            action.triggered.connect(lambda checked, n=name: self._on_quick_walkthrough(n))
            learn_menu.addAction(action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About TimeOS", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        disclaimer_action = QAction("&Disclaimer", self)
        disclaimer_action.triggered.connect(self._on_disclaimer)
        help_menu.addAction(disclaimer_action)

    def _setup_statusbar(self) -> None:
        """Set up the status bar."""
        statusbar = self.statusBar()

        # Causality indicator
        self._causality_label = QLabel()
        self._causality_label.setStyleSheet("color: #00ff88;")
        statusbar.addWidget(self._causality_label)

        # Spacer
        spacer = QWidget()
        spacer.setMinimumWidth(40)
        statusbar.addWidget(spacer)

        # Paradox risk
        self._paradox_label = QLabel()
        statusbar.addWidget(self._paradox_label)

        # Spacer
        spacer2 = QWidget()
        spacer2.setMinimumWidth(40)
        statusbar.addWidget(spacer2)

        # Anchor status
        self._anchor_label = QLabel()
        statusbar.addPermanentWidget(self._anchor_label)

        self._update_statusbar()

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self._control_panel.displace_requested.connect(self._on_displace)
        self._control_panel.return_requested.connect(self._on_return)
        self._control_panel.estop_requested.connect(self._on_emergency_stop)

        self._timeline_view.event_selected.connect(self._on_event_selected)

        self._model.state_changed.connect(self._on_state_changed)
        self._model.event_logged.connect(self._on_event_logged)

    def _start_update_timer(self) -> None:
        """Start the periodic update timer."""
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)
        self._update_timer.start(100)  # 10 Hz update rate

    def _on_update(self) -> None:
        """Periodic update handler."""
        self._model.update()
        self._update_statusbar()
        self._update_thermal_panel()

    def _update_statusbar(self) -> None:
        """Update status bar values."""
        state = self._model.get_state()

        # Causality
        causality = state.get("causality", "NOMINAL")
        if causality == "NOMINAL":
            self._causality_label.setText("CAUSALITY: ● NOMINAL")
            self._causality_label.setStyleSheet("color: #00ff88;")
        elif causality == "WARNING":
            self._causality_label.setText("CAUSALITY: ● WARNING")
            self._causality_label.setStyleSheet("color: #ffaa00;")
        else:
            self._causality_label.setText("CAUSALITY: ● VIOLATION")
            self._causality_label.setStyleSheet("color: #ff4444;")

        # Paradox risk
        risk = state.get("paradox_risk", 0.0) * 100
        color = "#00ff88" if risk < 1 else "#ffaa00" if risk < 5 else "#ff4444"
        self._paradox_label.setText(f"PARADOX RISK: {risk:.1f}%")
        self._paradox_label.setStyleSheet(f"color: {color};")

        # Anchor
        anchor_connected = state.get("anchor_connected", False)
        if anchor_connected:
            self._anchor_label.setText("ANCHOR: ● CONNECTED")
            self._anchor_label.setStyleSheet("color: #00ff88;")
        else:
            self._anchor_label.setText("ANCHOR: ○ DISCONNECTED")
            self._anchor_label.setStyleSheet("color: #5a5a5a;")

    def _update_thermal_panel(self) -> None:
        """Update thermal panel with current state."""
        if not self._thermal_panel:
            return

        state = self._model.get_state()

        temperature = state.get("temperature_kelvin", 4.2)
        quench_risk = state.get("quench_risk", 0.0)
        cooling_state = state.get("cooling_state", "cold")
        cooling_power = state.get("cooling_power", 0.0)

        # Get sensor readings if available
        sensors = {
            "mag_core": state.get("temp_magnet_core", temperature),
            "cryostat": state.get("temp_cryostat", temperature * 0.95),
            "shield": state.get("temp_shield", temperature * 1.1),
            "ambient": state.get("temp_ambient", 293.0),
        }

        self._thermal_panel.update_thermal(
            temperature=temperature,
            quench_risk=quench_risk,
            cooling_state=cooling_state,
            cooling_power=cooling_power,
            target_temp=4.2,
            critical_temp=9.2,
            sensors=sensors,
        )

    def _on_state_changed(self) -> None:
        """Handle state change from model."""
        pass  # Widgets update themselves

    def _on_event_logged(self, event: dict) -> None:
        """Handle new event from model."""
        pass  # Event log widget handles this

    def _on_event_selected(self, event: dict) -> None:
        """Handle event selection from timeline."""
        from timeos.gui.dialogs.event_details import EventDetailsDialog

        dialog = EventDetailsDialog(event, self)
        dialog.exec()

    def _on_new_session(self) -> None:
        """Start a new session."""
        reply = QMessageBox.question(
            self,
            "New Session",
            "Start a new session? Current state will be reset.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._model.reset()
            self._model.initialize()

    def _on_export_log(self) -> None:
        """Export event log."""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Event Log",
            "timeos_log.json",
            "JSON Files (*.json)",
        )
        if path:
            self._model.export_log(path)

    def _on_browse_scenarios(self) -> None:
        """Open scenario browser dialog."""
        from timeos.gui.dialogs.scenario_browser import ScenarioBrowserDialog

        dialog = ScenarioBrowserDialog(self)
        dialog.scenario_selected.connect(self._load_scenario)
        dialog.exec()

    def _on_quick_scenario(self, name: str) -> None:
        """Load a scenario by name."""
        self._load_scenario(name)

    def _load_scenario(self, name: str) -> None:
        """Load a scenario into the model."""
        try:
            from timeos.paradoxes import get_scenario

            scenario = get_scenario(name)
            if not scenario:
                QMessageBox.warning(self, "Error", f"Unknown scenario: {name}")
                return

            # Confirm if there are existing events
            if self._model.get_timeline_events():
                reply = QMessageBox.question(
                    self,
                    "Load Scenario",
                    f"Load '{scenario.title}'?\n\nThis will add events to the current timeline.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            # Load scenario into model's timeline
            event_map = self._model.load_scenario(scenario)

            QMessageBox.information(
                self,
                "Scenario Loaded",
                f"Loaded '{scenario.title}':\n"
                f"  {len(event_map)} events created\n"
                f"  Branches: {', '.join(scenario.branches) if scenario.branches else 'none'}",
            )

            # Refresh displays
            self._on_refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load scenario: {e}")

    def _on_open_walkthrough(self) -> None:
        """Open walkthrough dialog."""
        from timeos.gui.dialogs.walkthrough_dialog import WalkthroughDialog

        dialog = WalkthroughDialog(parent=self)
        dialog.load_scenario_requested.connect(self._load_scenario)
        dialog.show()  # Non-modal

    def _on_quick_walkthrough(self, scenario_name: str) -> None:
        """Open a specific walkthrough."""
        from timeos.gui.dialogs.walkthrough_dialog import WalkthroughDialog

        dialog = WalkthroughDialog(parent=self)
        dialog.load_scenario_requested.connect(self._load_scenario)
        dialog.set_walkthrough(scenario_name)
        dialog.show()  # Non-modal

    def _on_displace(self) -> None:
        """Open displacement dialog."""
        from timeos.gui.dialogs.displacement import DisplacementDialog

        dialog = DisplacementDialog(self._model, self)
        if dialog.exec():
            target = dialog.get_target()
            self._model.displace(target)

    def _on_return(self) -> None:
        """Return to anchor."""
        if not self._model.get_state().get("anchor_connected"):
            QMessageBox.warning(
                self,
                "No Anchor",
                "No anchor point set. Cannot return.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Return to Anchor",
            "Return to origin anchor point?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._model.return_to_anchor()

    def _on_emergency_stop(self) -> None:
        """Emergency stop."""
        self._model.emergency_stop()
        QMessageBox.warning(
            self,
            "EMERGENCY STOP",
            "Emergency stop activated.\nAll operations halted.",
        )

    def _on_reset_layout(self) -> None:
        """Reset window layout."""
        self.resize(1400, 900)
        self.move(100, 100)
        if self.isFullScreen():
            self.showNormal()
            self._fullscreen_action.setChecked(False)

    def _on_refresh(self) -> None:
        """Refresh all displays."""
        self._model.state_changed.emit()
        self._timeline_view._reset_view()

    def _on_toggle_fullscreen(self, checked: bool) -> None:
        """Toggle fullscreen mode."""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def _on_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About TimeOS Control",
            "<h2>TimeOS Control</h2>"
            "<p>Version 0.1.0</p>"
            "<p>Mission Control interface for temporal operations.</p>"
            "<p>Copyright &copy; 2024-2026 Skylark Software LLC. All Rights Reserved.</p>",
        )

    def _on_disclaimer(self) -> None:
        """Show disclaimer dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        from PySide6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("Temporal Control Framework - Disclaimer")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
<h2>TEMPORAL CONTROL FRAMEWORK - WARRANTY DISCLAIMER</h2>
<p><b>BY USING THIS SOFTWARE, YOU ACKNOWLEDGE THAT:</b></p>

<p><b>1. NO WARRANTY OF TIMELINE CONSISTENCY.</b> We make no guarantees that your
current timeline will remain your original timeline, that causality will be preserved,
or that you will continue to exist in a recognizable form.</p>

<p><b>2. PARADOX RISK.</b> You assume all responsibility for grandfather paradoxes,
bootstrap paradoxes, ontological paradoxes, and any other causal inconsistencies you
create. This includes but is not limited to: preventing your own birth, creating
stable time loops, or spawning divergent timelines.</p>

<p><b>3. BUTTERFLY EFFECTS.</b> Any temporal displacement, however minor, may result
in cascading changes to history. We are not liable for: altered election outcomes,
prevented inventions, erased relationships, or the complete collapse of civilization
as you knew it.</p>

<p><b>4. BRANCH COHERENCE.</b> Timeline branches are maintained on a best-effort basis.
We cannot guarantee you'll be able to return to your original branch, or that it will
still exist when you try.</p>

<p><b>5. CLOCK DRIFT CONSEQUENCES.</b> Microsecond-level synchronization errors may
result in arriving at the wrong moment, location, or universe. This is your problem.</p>

<p><b>6. ENERGY BUDGET VIOLATIONS.</b> Exceeding recommended energy parameters may
result in localized spacetime instabilities, singularity formation, or conversion of
matter into exotic states. Do not exceed 1.00e+15 J without adult supervision.</p>

<p><b>7. CAUSALITY MONITOR ACCURACY.</b> The causality monitoring system reports
violations based on best theoretical models. These models may be wrong. Violations
above 15% indicate you should probably stop, but we're not your parents.</p>

<p><b>8. DEMO MODE LIMITATIONS.</b> Demo mode uses simulated temporal physics.
Behavior in live mode may differ substantially. "It worked in demo mode" is not
a valid excuse.</p>

<p><b>9. ROS2 DEPENDENCIES.</b> This system assumes ROS2 message passing occurs in
chronological order. If you've managed to violate this assumption, congratulations,
you've broken something we didn't think was breakable.</p>

<p><b>10. NO TECHNICAL SUPPORT.</b> If you call for help, we may not exist yet,
anymore, or in your current timeline. Email T-Symmetry@skylarkSoftware.me with your
branch ID and hope we receive it.</p>

<p><b>11. ASSUMPTION OF RISK.</b> You accept full responsibility for: destroying
the universe, creating universe(s), merging timelines, splitting timelines, or
getting stuck in a causal loop.</p>

<p><b>12. RELEASE OF LIABILITY.</b> You release the developers from any claims
arising from temporal displacement, including claims that cannot yet be formulated
because the legal framework doesn't exist in your current temporal location.</p>

<hr>

<p><b>THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF TIMELINE STABILITY, FITNESS
FOR TEMPORAL TRAVEL, OR NON-VIOLATION OF CAUSALITY.</b></p>

<p><b>USE AT YOUR OWN RISK. SERIOUSLY.</b></p>

<hr>

<p><i>Skylark Software LLC is not responsible for any version of you that no longer exists.</i></p>
""")
        layout.addWidget(text)

        ok_btn = QPushButton("I Accept the Risks")
        ok_btn.clicked.connect(dialog.accept)
        layout.addWidget(ok_btn)

        dialog.exec()

    def _on_toggle_module(self, module_id: str, enabled: bool) -> None:
        """Toggle a hardware module on/off."""
        self._model.set_module_enabled(module_id, enabled)

    def _on_switch_mode(self) -> None:
        """Switch operating mode."""
        from timeos.gui.dialogs.mode_selector import ModeSelector

        selector = ModeSelector(self)
        if selector.exec() != ModeSelector.DialogCode.Accepted:
            return

        new_demo, new_emulated, new_ros2 = selector.get_mode()

        # Check if mode actually changed
        if (new_demo == self._demo and
            new_emulated == self._emulated and
            new_ros2 == self._ros2):
            return  # No change

        # Confirm restart
        reply = QMessageBox.question(
            self,
            "Switch Mode",
            f"Switch to {selector.get_mode_name().title()} mode?\n\n"
            "This will restart the application.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Restart with new mode
        import sys
        import subprocess

        # Build new command
        args = [sys.executable, "-m", "timeos", "gui"]
        if new_demo:
            args.append("--demo")
        if new_emulated:
            args.append("--emulated")
        if new_ros2:
            args.append("--ros2")

        # Start new process (detached)
        subprocess.Popen(
            args,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Close current application
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    def _on_hil_config(self) -> None:
        """Open HIL configuration dialog."""
        from timeos.gui.dialogs.hil_config_dialog import HILConfigDialog

        dialog = HILConfigDialog(self)
        dialog.config_changed.connect(self._on_hil_config_changed)
        dialog.exec()

    def _on_hil_config_changed(self, config: dict) -> None:
        """Handle HIL configuration changes."""
        # Apply configuration to model/hardware
        # For now, just show confirmation
        QMessageBox.information(
            self,
            "Configuration Applied",
            "HIL configuration has been updated.\n"
            "Some changes may require a restart to take effect.",
        )

    def _on_failure_injection(self) -> None:
        """Open failure injection dialog."""
        from timeos.gui.dialogs.failure_injection_dialog import FailureInjectionDialog

        dialog = FailureInjectionDialog(self)
        dialog.failure_injected.connect(self._on_failure_injected)
        dialog.failure_cleared.connect(self._on_failure_cleared)
        dialog.all_failures_cleared.connect(self._on_all_failures_cleared)
        dialog.exec()

    def _on_failure_injected(self, name: str, params: dict) -> None:
        """Handle failure injection."""
        # Would apply to emulated hardware here
        self.statusBar().showMessage(f"Failure injected: {name}", 5000)

    def _on_failure_cleared(self, name: str) -> None:
        """Handle failure cleared."""
        self.statusBar().showMessage(f"Failure cleared: {name}", 3000)

    def _on_all_failures_cleared(self) -> None:
        """Handle all failures cleared."""
        self.statusBar().showMessage("All failures cleared", 3000)

    def _on_data_logger(self) -> None:
        """Open data logger panel in a dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Data Logger")
        dialog.setMinimumSize(400, 500)

        layout = QVBoxLayout(dialog)
        logger_panel = DataLoggerPanel()
        layout.addWidget(logger_panel)

        dialog.exec()

    def _on_ros2_management(self) -> None:
        """Open ROS2 management dialog."""
        from timeos.gui.ros2 import ROS2ManagerDialog

        dialog = ROS2ManagerDialog(self)
        dialog.exec()

    def _on_show_hw_status(self) -> None:
        """Show detailed hardware status dialog."""
        from timeos.hardware.tiers import (
            get_module_spec,
            get_tier_symbol,
            get_tier_color,
            get_overall_buildability,
            format_cost_range,
        )

        state = self._model.get_state()
        statuses = self._model.get_module_statuses()

        # Build status text
        lines = ["<h3>Hardware Status</h3>"]

        # Mode
        mode_parts = []
        if self._model.is_demo:
            mode_parts.append("Demo")
        if self._model.is_emulated:
            mode_parts.append("Emulated")
        if not mode_parts:
            mode_parts.append("Simulated")
        lines.append(f"<p><b>Mode:</b> {' + '.join(mode_parts)}</p>")

        # Overall buildability
        buildability = get_overall_buildability()
        lines.append(f"<p><b>System Buildability:</b> {buildability:.0f}%</p>")

        lines.append("<h4>Module Status</h4>")
        lines.append("<table style='width:100%'>")
        lines.append("<tr><th>Module</th><th>Status</th><th>Tier</th><th>Build%</th></tr>")

        module_id_map = {
            "Field Generator": "field_generator",
            "TDU": "tdu",
            "Causality Monitor": "causality_monitor",
            "Anchor": "anchor",
            "Safety": "safety",
            "Thermal": "thermal",
        }

        for name, status in statuses.items():
            status_color = {
                "ACTIVE": "#00ff88",
                "NOMINAL": "#00ff88",
                "STANDBY": "#ffcc00",
                "WARNING": "#ff8800",
                "ERROR": "#ff4444",
                "OFFLINE": "#888888",
            }.get(status, "#cccccc")

            # Get tier info
            module_id = module_id_map.get(name, name.lower().replace(" ", "_"))
            spec = get_module_spec(module_id)
            if spec:
                tier_sym = get_tier_symbol(spec.tier)
                tier_color = get_tier_color(spec.tier)
                build_pct = spec.buildability_percent
            else:
                tier_sym = "[?]"
                tier_color = "#888888"
                build_pct = 0

            lines.append(
                f"<tr>"
                f"<td><b>{name}</b></td>"
                f"<td style='color:{status_color}'>{status}</td>"
                f"<td style='color:{tier_color}'>{tier_sym}</td>"
                f"<td>{build_pct}%</td>"
                f"</tr>"
            )
        lines.append("</table>")

        # Tier legend
        lines.append("<h4>Tier Legend</h4>")
        lines.append("<p style='font-size:10px'>")
        lines.append("<span style='color:#00ff88'>[R] Real</span> | ")
        lines.append("<span style='color:#44aaff'>[P] Proxy</span> | ")
        lines.append("<span style='color:#888888'>[I] Infrastructure</span> | ")
        lines.append("<span style='color:#aa88ff'>[A] Abstract</span>")
        lines.append("</p>")

        # Emulated-specific info
        if self._model.is_emulated:
            lines.append("<h4>Emulated Hardware</h4><ul>")
            lines.append(f"<li>Field: {state.get('field_strength', 0):.2f} T</li>")
            lines.append(f"<li>Temperature: {state.get('temperature_kelvin', 0):.2f} K</li>")
            lines.append(f"<li>Quench Risk: {state.get('quench_risk', 0) * 100:.1f}%</li>")
            lines.append(f"<li>Machine State: {state.get('machine_state', 'unknown')}</li>")
            lines.append(f"<li>Ramp State: {state.get('ramp_state', 'unknown')}</li>")
            lines.append("</ul>")

        QMessageBox.information(
            self,
            "Hardware Status",
            "".join(lines)
        )

    def _on_correlation(self) -> None:
        """Open stream correlation dialog."""
        from timeos.gui.dialogs.correlation_dialog import CorrelationDialog

        dialog = CorrelationDialog(self)
        dialog.exec()

    def _on_drift_monitor(self) -> None:
        """Open drift monitor dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        from timeos.gui.widgets.drift_plot import DriftPlotWidget

        dialog = QDialog(self)
        dialog.setWindowTitle("Clock Drift Monitor")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)
        drift_widget = DriftPlotWidget()
        layout.addWidget(drift_widget)

        # Add some demo data if in demo mode
        if self._demo:
            drift_widget.add_clock_source("ntp", "ntp")
            drift_widget.add_clock_source("system", "system")

            # Simulate some drift samples
            import random
            for i in range(50):
                offset = random.gauss(0, 50e-6)  # ~50µs jitter
                uncertainty = random.uniform(1e-6, 10e-6)
                drift_widget.add_sample("ntp", offset, uncertainty)

                offset2 = random.gauss(100e-6, 20e-6)  # 100µs offset
                drift_widget.add_sample("system", offset2, uncertainty * 2)

        dialog.exec()

    def _on_export_format(self, format_type: str) -> None:
        """Export timeline in specified format."""
        from PySide6.QtWidgets import QFileDialog

        # Get file extension and filter based on format
        extensions = {
            "json": ("JSON Files (*.json)", ".json"),
            "csv": ("CSV Files (*.csv)", ".csv"),
            "prov": ("Turtle Files (*.ttl)", ".ttl"),
            "influx": ("Text Files (*.txt)", ".txt"),
        }

        filter_str, ext = extensions.get(format_type, ("All Files (*)", ""))

        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Timeline as {format_type.upper()}",
            f"timeline{ext}",
            filter_str,
        )

        if not path:
            return

        try:
            events = self._model.get_timeline_events()

            if format_type == "json":
                import json
                with open(path, 'w') as f:
                    json.dump([e for e in events], f, indent=2, default=str)

            elif format_type == "csv":
                import csv
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["event_id", "timestamp", "uncertainty", "event_type", "branch_id"])
                    for e in events:
                        stamp = e.get("stamp", {})
                        writer.writerow([
                            e.get("event_id", ""),
                            stamp.get("t", 0),
                            stamp.get("t_uncertainty", 0),
                            e.get("event_type", ""),
                            e.get("branch_id", "main"),
                        ])

            elif format_type == "prov":
                # Generate W3C PROV-O Turtle
                lines = [
                    "@prefix prov: <http://www.w3.org/ns/prov#> .",
                    "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
                    "@prefix timeos: <http://timeos.example.org/ns#> .",
                    "",
                ]
                for e in events:
                    event_id = e.get("event_id", "unknown")
                    stamp = e.get("stamp", {})
                    lines.append(f"timeos:{event_id} a prov:Activity ;")
                    lines.append(f"    prov:startedAtTime \"{stamp.get('t', 0)}\"^^xsd:decimal ;")
                    parents = e.get("parents", [])
                    if parents:
                        parent_refs = ", ".join(f"timeos:{p}" for p in parents)
                        lines.append(f"    prov:wasInformedBy {parent_refs} ;")
                    lines.append(f"    timeos:eventType \"{e.get('event_type', '')}\" .")
                    lines.append("")

                with open(path, 'w') as f:
                    f.write("\n".join(lines))

            elif format_type == "influx":
                # Generate InfluxDB line protocol
                lines = []
                for e in events:
                    stamp = e.get("stamp", {})
                    t_ns = int(stamp.get("t", 0) * 1e9)
                    event_type = e.get("event_type", "unknown").replace(" ", "\\ ")
                    branch = e.get("branch_id", "main")
                    uncertainty = stamp.get("t_uncertainty", 0)
                    lines.append(
                        f"timeline_event,branch={branch},type={event_type} "
                        f"uncertainty={uncertainty} {t_ns}"
                    )

                with open(path, 'w') as f:
                    f.write("\n".join(lines))

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(events)} events to:\n{path}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _save_settings(self) -> None:
        """Save window state to settings."""
        settings = QSettings("Skylark Software LLC", "TimeOS Control")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def _restore_settings(self) -> None:
        """Restore window state from settings."""
        settings = QSettings("Skylark Software LLC", "TimeOS Control")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        # Escape key triggers emergency stop
        if event.key() == Qt.Key.Key_Escape:
            self._on_emergency_stop()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Handle window close."""
        self._save_settings()
        self._update_timer.stop()
        self._clock_panel.stop()
        self._model.shutdown()
        event.accept()
