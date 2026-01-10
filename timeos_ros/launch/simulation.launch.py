"""Launch file for TimeOS simulation mode.

Launches all nodes with emulated hardware for development and testing.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for simulation."""

    # Declare arguments
    db_path_arg = DeclareLaunchArgument(
        "db_path",
        default_value=":memory:",
        description="Path to timeline database (or :memory: for in-memory)",
    )

    max_field_arg = DeclareLaunchArgument(
        "max_field_tesla",
        default_value="10.0",
        description="Maximum field strength in Tesla",
    )

    publish_rate_arg = DeclareLaunchArgument(
        "publish_rate_hz",
        default_value="10.0",
        description="Status publish rate in Hz",
    )

    # Timeline node
    timeline_node = Node(
        package="timeos_ros",
        executable="timeline_node.py",
        name="timeline_node",
        parameters=[
            {"db_path": LaunchConfiguration("db_path")},
            {"author": "ros2_simulation"},
            {"publish_rate": LaunchConfiguration("publish_rate_hz")},
        ],
        output="screen",
    )

    # Field generator node
    field_generator_node = Node(
        package="timeos_ros",
        executable="field_generator_node.py",
        name="field_generator_node",
        parameters=[
            {"max_field_tesla": LaunchConfiguration("max_field_tesla")},
            {"ramp_rate_tesla_per_second": 0.1},
            {"operating_temp_kelvin": 4.2},
            {"publish_rate_hz": LaunchConfiguration("publish_rate_hz")},
            {"use_emulation": True},
        ],
        output="screen",
    )

    # TDU node
    tdu_node = Node(
        package="timeos_ros",
        executable="tdu_node.py",
        name="tdu_node",
        parameters=[
            {"max_displacement_years": 100.0},
            {"energy_per_second": 1.0e9},
            {"publish_rate_hz": LaunchConfiguration("publish_rate_hz")},
            {"use_emulation": True},
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
            {"publish_rate_hz": LaunchConfiguration("publish_rate_hz")},
        ],
        output="screen",
    )

    # Safety monitor node
    safety_node = Node(
        package="timeos_ros",
        executable="safety_monitor_node.py",
        name="safety_monitor_node",
        parameters=[
            {"max_temperature_kelvin": 9.0},
            {"max_risk_level": 0.30},
            {"publish_rate_hz": 20.0},  # Higher rate for safety
        ],
        output="screen",
    )

    return LaunchDescription([
        # Arguments
        db_path_arg,
        max_field_arg,
        publish_rate_arg,

        # Info
        LogInfo(msg="Launching TimeOS in SIMULATION mode"),
        LogInfo(msg="All hardware is emulated"),

        # Nodes
        timeline_node,
        field_generator_node,
        tdu_node,
        causality_node,
        safety_node,
    ])
