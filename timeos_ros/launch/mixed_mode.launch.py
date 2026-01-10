"""Launch file for TimeOS mixed mode.

Launches with configurable mix of real and emulated hardware.
Useful for hardware-in-the-loop testing.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, GroupAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for mixed mode."""

    # Declare arguments for each module
    db_path_arg = DeclareLaunchArgument(
        "db_path",
        default_value=":memory:",
        description="Path to timeline database",
    )

    field_emulated_arg = DeclareLaunchArgument(
        "field_emulated",
        default_value="true",
        description="Use emulated field generator",
    )

    tdu_emulated_arg = DeclareLaunchArgument(
        "tdu_emulated",
        default_value="true",
        description="Use emulated TDU",
    )

    publish_rate_arg = DeclareLaunchArgument(
        "publish_rate_hz",
        default_value="10.0",
        description="Status publish rate in Hz",
    )

    # Timeline node (always software)
    timeline_node = Node(
        package="timeos_ros",
        executable="timeline_node.py",
        name="timeline_node",
        parameters=[
            {"db_path": LaunchConfiguration("db_path")},
            {"author": "ros2_mixed"},
            {"publish_rate": LaunchConfiguration("publish_rate_hz")},
        ],
        output="screen",
    )

    # Field generator - emulated
    field_generator_emulated = Node(
        package="timeos_ros",
        executable="field_generator_node.py",
        name="field_generator_node",
        condition=IfCondition(LaunchConfiguration("field_emulated")),
        parameters=[
            {"max_field_tesla": 10.0},
            {"ramp_rate_tesla_per_second": 0.1},
            {"operating_temp_kelvin": 4.2},
            {"publish_rate_hz": LaunchConfiguration("publish_rate_hz")},
            {"use_emulation": True},
        ],
        output="screen",
    )

    # Field generator - hardware (stub)
    field_generator_hardware = Node(
        package="timeos_ros",
        executable="field_generator_node.py",
        name="field_generator_node",
        condition=UnlessCondition(LaunchConfiguration("field_emulated")),
        parameters=[
            {"max_field_tesla": 10.0},
            {"ramp_rate_tesla_per_second": 0.05},
            {"operating_temp_kelvin": 4.2},
            {"publish_rate_hz": 50.0},
            {"use_emulation": False},
        ],
        output="screen",
    )

    # TDU - emulated
    tdu_emulated = Node(
        package="timeos_ros",
        executable="tdu_node.py",
        name="tdu_node",
        condition=IfCondition(LaunchConfiguration("tdu_emulated")),
        parameters=[
            {"max_displacement_years": 100.0},
            {"energy_per_second": 1.0e9},
            {"publish_rate_hz": LaunchConfiguration("publish_rate_hz")},
            {"use_emulation": True},
        ],
        output="screen",
    )

    # TDU - hardware (stub)
    tdu_hardware = Node(
        package="timeos_ros",
        executable="tdu_node.py",
        name="tdu_node",
        condition=UnlessCondition(LaunchConfiguration("tdu_emulated")),
        parameters=[
            {"max_displacement_years": 100.0},
            {"energy_per_second": 1.0e9},
            {"publish_rate_hz": 50.0},
            {"use_emulation": False},
        ],
        output="screen",
    )

    # Causality monitor (always software)
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

    # Safety monitor (always active)
    safety_node = Node(
        package="timeos_ros",
        executable="safety_monitor_node.py",
        name="safety_monitor_node",
        parameters=[
            {"max_temperature_kelvin": 9.0},
            {"max_risk_level": 0.30},
            {"publish_rate_hz": 20.0},
        ],
        output="screen",
    )

    return LaunchDescription([
        # Arguments
        db_path_arg,
        field_emulated_arg,
        tdu_emulated_arg,
        publish_rate_arg,

        # Info
        LogInfo(msg="Launching TimeOS in MIXED mode"),
        LogInfo(msg="Configure individual modules as emulated or hardware"),

        # Nodes
        safety_node,
        timeline_node,
        field_generator_emulated,
        field_generator_hardware,
        tdu_emulated,
        tdu_hardware,
        causality_node,
    ])
