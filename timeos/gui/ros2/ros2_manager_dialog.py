"""ROS2 Manager Dialog - Main dialog for ROS2 system management."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPushButton,
    QLabel,
    QFrame,
    QSplitter,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt

from .ros2_bridge import ROS2Bridge
from .ros2_status_panel import ROS2StatusPanel
from .node_manager_widget import NodeManagerWidget
from .topic_monitor_widget import TopicMonitorWidget
from .service_call_widget import ServiceCallWidget


class ROS2ManagerDialog(QDialog):
    """Main dialog for ROS2 system management.

    Provides tabbed interface for:
    - Node management (launch/stop)
    - Topic monitoring
    - Service calling
    - System status
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("ROS2 Management")
        self.setMinimumSize(900, 700)

        # Create bridge
        self._bridge = ROS2Bridge(self)

        self._setup_ui()

        # Start auto-refresh if ROS2 available
        if self._bridge.ros2_available:
            self._bridge.start_refresh(2000)

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)

        # Main content with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Status
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._status_panel = ROS2StatusPanel(self._bridge)
        left_layout.addWidget(self._status_panel)
        left_layout.addStretch()

        splitter.addWidget(left_panel)

        # Right panel - Tabs
        self._tabs = QTabWidget()

        # Nodes tab
        self._node_widget = NodeManagerWidget(self._bridge)
        self._tabs.addTab(self._node_widget, "Nodes")

        # Topics tab
        self._topic_widget = TopicMonitorWidget(self._bridge)
        self._tabs.addTab(self._topic_widget, "Topics")

        # Services tab
        self._service_widget = ServiceCallWidget(self._bridge)
        self._tabs.addTab(self._service_widget, "Services")

        splitter.addWidget(self._tabs)

        # Set splitter sizes (status panel narrower)
        splitter.setSizes([250, 650])

        layout.addWidget(splitter, 1)

        # Bottom bar
        bottom_layout = QHBoxLayout()

        # Status info
        self._info_label = QLabel()
        self._update_info_label()
        bottom_layout.addWidget(self._info_label)

        bottom_layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox()

        refresh_btn = QPushButton("Refresh All")
        refresh_btn.clicked.connect(self._on_refresh_all)
        button_box.addButton(refresh_btn, QDialogButtonBox.ButtonRole.ActionRole)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_box.addButton(close_btn, QDialogButtonBox.ButtonRole.AcceptRole)

        bottom_layout.addWidget(button_box)

        layout.addLayout(bottom_layout)

        # Connect signals
        self._bridge.ros2_available_changed.connect(self._on_ros2_changed)
        self._bridge.nodes_updated.connect(self._on_nodes_updated)
        self._bridge.error_occurred.connect(self._on_error)

    def _update_info_label(self) -> None:
        """Update the info label."""
        if self._bridge.ros2_available:
            node_count = len(self._bridge.nodes)
            topic_count = len(self._bridge.topics)
            service_count = len(self._bridge.services)
            running = self._bridge.get_running_launches()

            info = f"Nodes: {node_count} | Topics: {topic_count} | Services: {service_count}"
            if running:
                info += f" | Running: {', '.join(running)}"

            self._info_label.setText(info)
            self._info_label.setStyleSheet("color: #00ff88;")
        else:
            self._info_label.setText(
                "ROS2 not available. Source the timeos-ros conda environment."
            )
            self._info_label.setStyleSheet("color: #ff8888;")

    def _on_ros2_changed(self, available: bool) -> None:
        """Handle ROS2 availability change."""
        self._update_info_label()

    def _on_nodes_updated(self, nodes: list) -> None:
        """Handle nodes update."""
        self._update_info_label()

    def _on_refresh_all(self) -> None:
        """Refresh all data."""
        self._bridge.refresh_all()

    def _on_error(self, error: str) -> None:
        """Handle error."""
        # Could show in status bar
        pass

    def closeEvent(self, event) -> None:
        """Handle close event."""
        # Stop auto-refresh
        self._bridge.stop_refresh()

        # Note: We don't shut down launches on dialog close
        # They continue running independently

        event.accept()

    def reject(self) -> None:
        """Handle dialog rejection (Escape key)."""
        self._bridge.stop_refresh()
        super().reject()

    def accept(self) -> None:
        """Handle dialog acceptance."""
        self._bridge.stop_refresh()
        super().accept()
