"""Launch file for TimeOS hardware mode.

Launches nodes configured for real hardware interfaces.
Note: Actual hardware drivers are not yet implemented.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for hardware mode."""

    # Declare arguments
    db_path_arg = DeclareLaunchArgument(
        "db_path",
        default_value="/var/lib/timeos/timeline.db",
        description="Path to timeline database",
    )

    device_prefix_arg = DeclareLaunchArgument(
        "device_prefix",
        default_value="/dev/timeos",
        description="Prefix for hardware device files",
    )

    safety_enabled_arg = DeclareLaunchArgument(
        "safety_enabled",
        default_value="true",
        description="Enable safety interlocks",
    )

    # Timeline node (same as simulation)
    timeline_node = Node(
        package="timeos_ros",
        executable="timeline_node.py",
        name="timeline_node",
        parameters=[
            {"db_path": LaunchConfiguration("db_path")},
            {"author": "ros2_hardware"},
            {"publish_rate": 50.0},  # Higher rate for hardware
        ],
        output="screen",
    )

    # Field generator node (hardware mode - stub for now)
    field_generator_node = Node(
        package="timeos_ros",
        executable="field_generator_node.py",
        name="field_generator_node",
        parameters=[
            {"max_field_tesla": 10.0},
            {"ramp_rate_tesla_per_second": 0.05},  # Slower for real hardware
            {"operating_temp_kelvin": 4.2},
            {"publish_rate_hz": 50.0},
            {"use_emulation": False},  # Would use real hardware
            # {"device_path": [LaunchConfiguration("device_prefix"), "/field"]},
        ],
        output="screen",
    )

    # TDU node (hardware mode - stub for now)
    tdu_node = Node(
        package="timeos_ros",
        executable="tdu_node.py",
        name="tdu_node",
        parameters=[
            {"max_displacement_years": 100.0},
            {"energy_per_second": 1.0e9},
            {"publish_rate_hz": 50.0},
            {"use_emulation": False},
        ],
        output="screen",
    )

    # Causality monitor node
    causality_node = Node(
        package="timeos_ros",
        executable="causality_monitor_node.py",
        name="causality_monitor_node",
        parameters=[
            {"risk_threshold_warning": 0.05},
            {"risk_threshold_branch": 0.15},
            {"risk_threshold_reject": 0.30},
            {"publish_rate_hz": 50.0},
        ],
        output="screen",
    )

    # Safety monitor node (critical for hardware)
    safety_node = Node(
        package="timeos_ros",
        executable="safety_monitor_node.py",
        name="safety_monitor_node",
        parameters=[
            {"max_temperature_kelvin": 8.5},  # More conservative for real HW
            {"max_risk_level": 0.25},
            {"publish_rate_hz": 100.0},  # High rate for safety
        ],
        output="screen",
    )

    return LaunchDescription([
        # Arguments
        db_path_arg,
        device_prefix_arg,
        safety_enabled_arg,

        # Warnings
        LogInfo(msg="==========================================="),
        LogInfo(msg="  LAUNCHING TimeOS in HARDWARE mode"),
        LogInfo(msg="  Real hardware interfaces will be used"),
        LogInfo(msg="  Ensure all safety systems are operational"),
        LogInfo(msg="==========================================="),

        # Nodes
        safety_node,  # Start safety first
        timeline_node,
        field_generator_node,
        tdu_node,
        causality_node,
    ])
