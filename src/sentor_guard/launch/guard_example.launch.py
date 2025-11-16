"""Example launch file for sentor_guard."""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    """Generate launch description for sentor_guard example."""
    pkg_share = get_package_share_directory('sentor_guard')
    
    guard_params_file = os.path.join(pkg_share, 'config', 'guard_params.yaml')
    
    return LaunchDescription([
        DeclareLaunchArgument(
            'guard_params',
            default_value=guard_params_file,
            description='Path to guard parameters file'
        ),
        
        # Launch lifecycle guard node
        Node(
            package='sentor_guard',
            executable='lifecycle_guard_node',
            name='lifecycle_guard',
            output='screen',
            parameters=[
                LaunchConfiguration('guard_params'),
                {
                    'managed_nodes': ['/controller_server', '/planner_server'],
                    'check_rate': 10.0,
                }
            ],
        ),
        
        # Example: Topic guard for cmd_vel
        Node(
            package='sentor_guard',
            executable='topic_guard_node',
            name='cmd_vel_guard',
            output='screen',
            parameters=[
                LaunchConfiguration('guard_params'),
                {
                    'input_topic': '/nav2/cmd_vel',
                    'output_topic': '/cmd_vel',
                    'message_type': 'geometry_msgs/msg/Twist',
                }
            ],
        ),
    ])
