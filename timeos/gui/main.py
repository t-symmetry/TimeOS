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
from timeos.gui.widgets.field_monitor import FieldMonitor
from timeos.gui.widgets.timeline_view import TimelineView
from timeos.gui.widgets.event_log import EventLogWidget
from timeos.gui.widgets.control_panel import ControlPanel
from timeos.gui.models.machine_model import MachineModel


class MainWindow(QMainWindow):
    """Main window for TimeOS Control application."""

    def __init__(self, demo: bool = False, parent: QWidget | None = None):
        super().__init__(parent)

        self._demo = demo
        self._model = MachineModel(demo=demo)

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
        self.setWindowTitle("TimeOS Control")
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

        # Field monitor
        self._field_monitor = FieldMonitor(self._model)
        layout.addWidget(self._field_monitor)

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
        reset_layout_action.triggered.connect(self._on_reset_layout)
        view_menu.addAction(reset_layout_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About TimeOS", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

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

    def _on_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About TimeOS Control",
            "<h2>TimeOS Control</h2>"
            "<p>Version 0.1.0</p>"
            "<p>Mission Control interface for temporal operations.</p>"
            "<p>&copy; T-Symmetry Labs</p>"
            "<p>Licensed under Apache 2.0</p>",
        )

    def _save_settings(self) -> None:
        """Save window state to settings."""
        settings = QSettings("T-Symmetry Labs", "TimeOS Control")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def _restore_settings(self) -> None:
        """Restore window state from settings."""
        settings = QSettings("T-Symmetry Labs", "TimeOS Control")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event) -> None:
        """Handle window close."""
        self._save_settings()
        self._update_timer.stop()
        self._model.shutdown()
        event.accept()
