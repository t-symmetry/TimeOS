#!/usr/bin/env python3
"""Launch file for T-symmetry experiments.

This launches all nodes required for a T-symmetry measurement experiment:
- Field generator control
- Thermal monitoring
- Sensor aggregation
- T-symmetry analyzer
- Safety monitoring
- Data recording
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace


def generate_launch_description():
    # Arguments
    use_sim = DeclareLaunchArgument(
        'use_sim',
        default_value='true',
        description='Use simulated/emulated hardware'
    )

    namespace = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Namespace for all nodes'
    )

    output_dir = DeclareLaunchArgument(
        'output_dir',
        default_value='/tmp/timeos_experiments',
        description='Directory for experiment data output'
    )

    # Core hardware nodes
    field_generator = Node(
        package='timeos_ros',
        executable='field_generator_node',
        name='field_generator',
        parameters=[{
            'use_emulated': LaunchConfiguration('use_sim'),
            'publish_rate': 10.0,
            'max_field_tesla': 15.0,
            'max_ramp_rate': 0.1,
        }],
        output='screen',
    )

    thermal_monitor = Node(
        package='timeos_ros',
        executable='thermal_monitor_node',
        name='thermal_monitor',
        parameters=[{
            'base_temperature': 4.2,
        }],
        output='screen',
    )

    safety_monitor = Node(
        package='timeos_ros',
        executable='safety_monitor_node',
        name='safety_monitor',
        parameters=[{
            'watchdog_timeout_ms': 1000.0,
            'max_field_tesla': 15.0,
            'max_temperature_kelvin': 10.0,
        }],
        output='screen',
    )

    anchor = Node(
        package='timeos_ros',
        executable='anchor_node',
        name='anchor',
        output='screen',
    )

    # Sensor nodes
    sensor_aggregator = Node(
        package='timeos_ros',
        executable='sensor_aggregator_node',
        name='sensor_aggregator',
        parameters=[{
            'emulate_sensors': LaunchConfiguration('use_sim'),
            'default_sample_rate': 100.0,
        }],
        output='screen',
    )

    # Analysis nodes
    t_symmetry_analyzer = Node(
        package='timeos_ros',
        executable='t_symmetry_analyzer_node',
        name='t_symmetry_analyzer',
        parameters=[{
            'sample_window_sec': 10.0,
            'min_samples': 100,
            'significance_threshold': 3.0,
            'sensor_topics': [
                '/timeos/sensors/magnetometer_z',
                '/timeos/sensors/magnetometer_x',
                '/timeos/sensors/magnetometer_y',
            ],
        }],
        output='screen',
    )

    # Support nodes
    timeline = Node(
        package='timeos_ros',
        executable='timeline_node',
        name='timeline',
        parameters=[{
            'db_path': ':memory:',
            'publish_rate': 10.0,
        }],
        output='screen',
    )

    causality_monitor = Node(
        package='timeos_ros',
        executable='causality_monitor_node',
        name='causality_monitor',
        output='screen',
    )

    experiment_controller = Node(
        package='timeos_ros',
        executable='experiment_controller_node',
        name='experiment_controller',
        output='screen',
    )

    data_recorder = Node(
        package='timeos_ros',
        executable='data_recorder_node',
        name='data_recorder',
        parameters=[{
            'output_dir': LaunchConfiguration('output_dir'),
            'buffer_size': 100000,
        }],
        output='screen',
    )

    return LaunchDescription([
        use_sim,
        namespace,
        output_dir,
        # Hardware
        field_generator,
        thermal_monitor,
        safety_monitor,
        anchor,
        # Sensors
        sensor_aggregator,
        # Analysis
        t_symmetry_analyzer,
        # Support
        timeline,
        causality_monitor,
        experiment_controller,
        data_recorder,
    ])
