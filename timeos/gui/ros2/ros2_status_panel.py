"""ROS2 Status Panel - LED indicators for ROS2 node status."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
)
from PySide6.QtCore import Qt

from .ros2_bridge import ROS2Bridge, TIMEOS_NODES


class ROS2NodeLED(QWidget):
    """LED-style status indicator for ROS2 nodes."""

    COLORS = {
        "running": "#00ff88",      # Green
        "starting": "#ffff00",     # Yellow
        "stopping": "#ffaa00",     # Orange
        "stopped": "#5a5a5a",      # Gray
        "error": "#ff4444",        # Red
        "not_responding": "#ff8800",  # Orange
        "unknown": "#5a5a5a",      # Gray
    }

    STATUS_LABELS = {
        "running": "RUNNING",
        "starting": "STARTING",
        "stopping": "STOPPING",
        "stopped": "STOPPED",
        "error": "ERROR",
        "not_responding": "NO RESP",
        "unknown": "UNKNOWN",
    }

    def __init__(
        self,
        node_name: str,
        display_name: str = "",
        tooltip: str = "",
        parent: QWidget | None = None
    ):
        super().__init__(parent)

        self._node_name = node_name
        self._status = "unknown"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # LED indicator
        self._led = QLabel()
        self._led.setFixedSize(10, 10)
        self._led.setStyleSheet(self._led_style("#5a5a5a"))
        layout.addWidget(self._led)

        # Label
        display = display_name or node_name.replace('_', ' ').title()
        self._label = QLabel(display)
        self._label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        self._label.setMinimumWidth(100)
        if tooltip:
            self._label.setToolTip(tooltip)
        layout.addWidget(self._label)

        # Status text
        self._status_label = QLabel("UNKNOWN")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._status_label.setStyleSheet(
            "color: #5a5a5a; font-family: monospace; font-size: 10px;"
        )
        self._status_label.setMinimumWidth(60)
        layout.addWidget(self._status_label)

    @property
    def node_name(self) -> str:
        """Get the node name."""
        return self._node_name

    @property
    def status(self) -> str:
        """Get current status."""
        return self._status

    def set_status(self, status: str) -> None:
        """Set the status and update display."""
        self._status = status
        color = self.COLORS.get(status, "#5a5a5a")
        label = self.STATUS_LABELS.get(status, status.upper())

        self._led.setStyleSheet(self._led_style(color))
        self._status_label.setText(label)
        self._status_label.setStyleSheet(
            f"color: {color}; font-family: monospace; font-size: 10px;"
        )

    def _led_style(self, color: str) -> str:
        """Generate LED stylesheet."""
        return f"""
            background-color: {color};
            border-radius: 5px;
            border: 1px solid {color};
        """


class ROS2StatusPanel(QGroupBox):
    """ROS2 system status panel with LED indicators for TimeOS nodes."""

    NODE_TOOLTIPS = {
        'timeline': 'Temporal event log and timeline management',
        'field_generator': 'Electromagnetic field control',
        'safety_monitor': 'Safety interlocks and E-stop',
        'thermal_monitor': 'Cryogenic temperature monitoring',
        'anchor': 'Temporal reference and synchronization',
        'tdu': 'Temporal Displacement Unit control',
        'causality_monitor': 'Causality constraint checking',
        't_symmetry_analyzer': 'T-symmetry measurement and analysis',
        'sensor_aggregator': 'Multi-sensor data aggregation',
        'experiment_controller': 'Experiment orchestration',
        'data_recorder': 'Data logging and recording',
    }

    def __init__(
        self,
        bridge: ROS2Bridge,
        parent: QWidget | None = None
    ):
        super().__init__("ROS2 Nodes", parent)

        self._bridge = bridge
        self._node_leds: Dict[str, ROS2NodeLED] = {}

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        # ROS2 availability indicator
        self._ros2_status = QLabel()
        self._update_ros2_status()
        layout.addWidget(self._ros2_status)

        # Node LEDs
        for node_name in TIMEOS_NODES.keys():
            tooltip = self.NODE_TOOLTIPS.get(node_name, '')
            led = ROS2NodeLED(node_name, tooltip=tooltip)
            self._node_leds[node_name] = led
            layout.addWidget(led)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(80)
        refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _connect_signals(self) -> None:
        """Connect bridge signals."""
        self._bridge.ros2_available_changed.connect(self._on_ros2_available_changed)
        self._bridge.nodes_updated.connect(self._on_nodes_updated)

    def _update_ros2_status(self) -> None:
        """Update ROS2 availability display."""
        if self._bridge.ros2_available:
            self._ros2_status.setText("ROS2: Available")
            self._ros2_status.setStyleSheet(
                "color: #00ff88; font-weight: bold; padding: 4px;"
            )
        else:
            self._ros2_status.setText("ROS2: Not Available")
            self._ros2_status.setStyleSheet(
                "color: #ff4444; font-weight: bold; padding: 4px;"
            )

    def _on_ros2_available_changed(self, available: bool) -> None:
        """Handle ROS2 availability change."""
        self._update_ros2_status()
        if not available:
            # Set all nodes to unknown
            for led in self._node_leds.values():
                led.set_status("unknown")

    def _on_nodes_updated(self, nodes: list) -> None:
        """Handle node list update."""
        status = self._bridge.get_timeos_nodes_status()
        for node_name, node_status in status.items():
            if node_name in self._node_leds:
                self._node_leds[node_name].set_status(node_status)

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        self._bridge.get_node_list()

    def get_node_status(self, node_name: str) -> str:
        """Get status of a specific node."""
        if node_name in self._node_leds:
            return self._node_leds[node_name].status
        return "unknown"

    def update_all(self) -> None:
        """Force update of all node statuses."""
        self._on_nodes_updated(self._bridge.nodes)
