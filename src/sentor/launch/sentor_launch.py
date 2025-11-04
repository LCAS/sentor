#!/usr/bin/env python3
"""
ROS2 Launch file for Sentor monitoring system.

This launch file starts the sentor_node with the default test_monitor_config.yaml configuration.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate the launch description for the sentor monitoring system."""
    
    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=PathJoinSubstitution([
            FindPackageShare('sentor'),
            'config',
            'test_monitor_config.yaml'
        ]),
        description='Path to the YAML configuration file for sentor monitoring'
    )
    
    log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        description='Log level for the sentor node (debug, info, warn, error, fatal)'
    )
    
    # Define the sentor node
    sentor_node = Node(
        package='sentor',
        executable='sentor_node.py',
        name='sentor',
        output='screen',
        parameters=[{
            'config_file': LaunchConfiguration('config_file')
        }],
        arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')],
        remappings=[
            # Add any topic remappings here if needed
        ]
    )
    
    return LaunchDescription([
        config_file_arg,
        log_level_arg,
        sentor_node,
    ])
