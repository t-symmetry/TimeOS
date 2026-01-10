#!/usr/bin/env python3
"""Minimal launch file - just core nodes for testing."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='timeos_ros',
            executable='timeline_node',
            name='timeline',
            output='screen',
        ),
        Node(
            package='timeos_ros',
            executable='safety_monitor_node',
            name='safety_monitor',
            output='screen',
        ),
        Node(
            package='timeos_ros',
            executable='field_generator_node',
            name='field_generator',
            parameters=[{'use_emulated': True}],
            output='screen',
        ),
    ])
