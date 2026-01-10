"""Node Manager Widget - Launch and manage ROS2 nodes."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from .ros2_bridge import ROS2Bridge, LAUNCH_CONFIGS, TIMEOS_NODES
from .ros2_status_panel import ROS2NodeLED


class LaunchConfigWidget(QGroupBox):
    """Widget for a single launch configuration."""

    launch_requested = Signal(str)  # config_name
    stop_requested = Signal(str)    # config_name

    def __init__(
        self,
        config_name: str,
        bridge: ROS2Bridge,
        parent: QWidget | None = None
    ):
        config = LAUNCH_CONFIGS[config_name]
        super().__init__(config['name'], parent)

        self._config_name = config_name
        self._bridge = bridge
        self._is_running = False

        self._setup_ui(config)
        self._connect_signals()

    def _setup_ui(self, config: dict) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)

        # Description
        desc_label = QLabel(config['description'])
        desc_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Nodes list
        nodes_text = ", ".join(config['nodes'])
        nodes_label = QLabel(f"Nodes: {nodes_text}")
        nodes_label.setStyleSheet("color: #808080; font-size: 10px;")
        nodes_label.setWordWrap(True)
        layout.addWidget(nodes_label)

        # Control buttons
        btn_layout = QHBoxLayout()

        self._start_btn = QPushButton("Start")
        self._start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d5a2d;
                color: white;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3d7a3d;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
        """)
        self._start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a2d2d;
                color: white;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7a3d3d;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
        """)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self._stop_btn)

        btn_layout.addStretch()

        # Status label
        self._status_label = QLabel("Stopped")
        self._status_label.setStyleSheet("color: #808080;")
        btn_layout.addWidget(self._status_label)

        layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        """Connect bridge signals."""
        self._bridge.launch_started.connect(self._on_launch_started)
        self._bridge.launch_stopped.connect(self._on_launch_stopped)
        self._bridge.ros2_available_changed.connect(self._on_ros2_changed)

    def _on_start(self) -> None:
        """Handle start button click."""
        self.launch_requested.emit(self._config_name)

    def _on_stop(self) -> None:
        """Handle stop button click."""
        self.stop_requested.emit(self._config_name)

    def _on_launch_started(self, config_name: str) -> None:
        """Handle launch started."""
        if config_name == self._config_name:
            self._is_running = True
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self._status_label.setText("Running")
            self._status_label.setStyleSheet("color: #00ff88;")

    def _on_launch_stopped(self, config_name: str) -> None:
        """Handle launch stopped."""
        if config_name == self._config_name:
            self._is_running = False
            self._start_btn.setEnabled(True)
            self._stop_btn.setEnabled(False)
            self._status_label.setText("Stopped")
            self._status_label.setStyleSheet("color: #808080;")

    def _on_ros2_changed(self, available: bool) -> None:
        """Handle ROS2 availability change."""
        self._start_btn.setEnabled(available and not self._is_running)

    @property
    def is_running(self) -> bool:
        """Whether this launch is running."""
        return self._is_running


class NodeManagerWidget(QWidget):
    """Widget for managing ROS2 nodes and launches."""

    def __init__(
        self,
        bridge: ROS2Bridge,
        parent: QWidget | None = None
    ):
        super().__init__(parent)

        self._bridge = bridge
        self._launch_widgets: Dict[str, LaunchConfigWidget] = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)

        # ROS2 status banner
        self._status_banner = QLabel()
        self._update_status_banner()
        layout.addWidget(self._status_banner)

        # Launch configurations
        launches_group = QGroupBox("Launch Configurations")
        launches_layout = QVBoxLayout(launches_group)

        for config_name in LAUNCH_CONFIGS:
            widget = LaunchConfigWidget(config_name, self._bridge)
            widget.launch_requested.connect(self._on_launch_requested)
            widget.stop_requested.connect(self._on_stop_requested)
            self._launch_widgets[config_name] = widget
            launches_layout.addWidget(widget)

        layout.addWidget(launches_group)

        # Node status table
        nodes_group = QGroupBox("Node Status")
        nodes_layout = QVBoxLayout(nodes_group)

        self._node_table = QTableWidget()
        self._node_table.setColumnCount(3)
        self._node_table.setHorizontalHeaderLabels(["Node", "Status", "Description"])
        self._node_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._node_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._node_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._node_table.setAlternatingRowColors(True)
        self._node_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._populate_node_table()
        nodes_layout.addWidget(self._node_table)

        # Refresh button
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self._on_refresh)
        nodes_layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(nodes_group)

    def _connect_signals(self) -> None:
        """Connect bridge signals."""
        self._bridge.ros2_available_changed.connect(self._on_ros2_changed)
        self._bridge.nodes_updated.connect(self._on_nodes_updated)
        self._bridge.error_occurred.connect(self._on_error)

    def _update_status_banner(self) -> None:
        """Update the ROS2 status banner."""
        if self._bridge.ros2_available:
            self._status_banner.setText(
                "ROS2 environment detected. Ready to launch nodes."
            )
            self._status_banner.setStyleSheet("""
                QLabel {
                    background-color: #1a3a1a;
                    color: #00ff88;
                    padding: 8px;
                    border-radius: 4px;
                }
            """)
        else:
            self._status_banner.setText(
                "ROS2 not available. Source the ROS2 environment and restart."
            )
            self._status_banner.setStyleSheet("""
                QLabel {
                    background-color: #3a1a1a;
                    color: #ff8888;
                    padding: 8px;
                    border-radius: 4px;
                }
            """)

    def _populate_node_table(self) -> None:
        """Populate the node status table."""
        descriptions = {
            'timeline': 'Temporal event log and timeline management',
            'field_generator': 'Electromagnetic field control',
            'safety_monitor': 'Safety interlocks and emergency stop',
            'thermal_monitor': 'Cryogenic temperature monitoring',
            'anchor': 'Temporal reference synchronization',
            'tdu': 'Temporal Displacement Unit control',
            'causality_monitor': 'Causality constraint validation',
            't_symmetry_analyzer': 'T-symmetry measurement analysis',
            'sensor_aggregator': 'Multi-sensor data aggregation',
            'experiment_controller': 'Experiment orchestration',
            'data_recorder': 'Data logging to HDF5/CSV',
        }

        self._node_table.setRowCount(len(TIMEOS_NODES))

        for row, (short_name, full_name) in enumerate(TIMEOS_NODES.items()):
            # Node name
            name_item = QTableWidgetItem(short_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._node_table.setItem(row, 0, name_item)

            # Status
            status_item = QTableWidgetItem("STOPPED")
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_item.setForeground(Qt.GlobalColor.gray)
            self._node_table.setItem(row, 1, status_item)

            # Description
            desc = descriptions.get(short_name, '')
            desc_item = QTableWidgetItem(desc)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._node_table.setItem(row, 2, desc_item)

    def _on_ros2_changed(self, available: bool) -> None:
        """Handle ROS2 availability change."""
        self._update_status_banner()

    def _on_nodes_updated(self, nodes: list) -> None:
        """Handle node list update."""
        status = self._bridge.get_timeos_nodes_status()

        for row in range(self._node_table.rowCount()):
            name_item = self._node_table.item(row, 0)
            status_item = self._node_table.item(row, 1)

            if name_item and status_item:
                node_name = name_item.text()
                node_status = status.get(node_name, 'stopped')

                status_item.setText(node_status.upper())

                if node_status == 'running':
                    status_item.setForeground(Qt.GlobalColor.green)
                elif node_status == 'error':
                    status_item.setForeground(Qt.GlobalColor.red)
                else:
                    status_item.setForeground(Qt.GlobalColor.gray)

    def _on_launch_requested(self, config_name: str) -> None:
        """Handle launch request."""
        if not self._bridge.ros2_available:
            QMessageBox.warning(
                self,
                "ROS2 Not Available",
                "ROS2 environment is not available.\n"
                "Source the ROS2 environment and restart the application."
            )
            return

        success = self._bridge.launch(config_name)
        if not success:
            QMessageBox.warning(
                self,
                "Launch Failed",
                f"Failed to launch {config_name} configuration."
            )

    def _on_stop_requested(self, config_name: str) -> None:
        """Handle stop request."""
        self._bridge.stop_launch(config_name)

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        self._bridge.get_node_list()

    def _on_error(self, error: str) -> None:
        """Handle error from bridge."""
        # Could show in status bar or log
        pass

    def shutdown(self) -> None:
        """Clean shutdown."""
        # Stop all running launches
        for config_name, widget in self._launch_widgets.items():
            if widget.is_running:
                self._bridge.stop_launch(config_name)
