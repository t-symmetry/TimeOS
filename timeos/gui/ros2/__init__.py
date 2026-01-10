"""ROS2 integration for TimeOS GUI.

This module provides subprocess-based ROS2 management capabilities
without requiring rclpy in the GUI process.
"""

from .ros2_bridge import (
    ROS2Bridge,
    NodeInfo,
    TopicInfo,
    ServiceInfo,
    TIMEOS_NODES,
    LAUNCH_CONFIGS,
    PRIORITY_TOPICS,
    PRIORITY_SERVICES,
)
from .ros2_status_panel import ROS2StatusPanel, ROS2NodeLED
from .node_manager_widget import NodeManagerWidget
from .topic_monitor_widget import TopicMonitorWidget
from .service_call_widget import ServiceCallWidget
from .ros2_manager_dialog import ROS2ManagerDialog

__all__ = [
    # Bridge
    'ROS2Bridge',
    'NodeInfo',
    'TopicInfo',
    'ServiceInfo',
    'TIMEOS_NODES',
    'LAUNCH_CONFIGS',
    'PRIORITY_TOPICS',
    'PRIORITY_SERVICES',
    # Widgets
    'ROS2StatusPanel',
    'ROS2NodeLED',
    'NodeManagerWidget',
    'TopicMonitorWidget',
    'ServiceCallWidget',
    # Dialog
    'ROS2ManagerDialog',
]
