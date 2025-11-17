"""
Example launch file for Nav2 with sentor_guard integration.

This demonstrates how to configure Nav2 bt_navigator to use the sentor_guard
BT condition node. The key steps are:
1. Add sentor_guard_bt_nodes library to bt_navigator plugin list
2. Specify a behavior tree XML that uses CheckAutonomyAllowed
3. Ensure required topics are published (state, mode, heartbeats)

This is a minimal example - in a real system you would include the full
Nav2 stack launch configuration.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    # Get package directories
    sentor_guard_dir = get_package_share_directory('sentor_guard')
    
    # Declare launch arguments
    behavior_tree_xml = LaunchConfiguration('behavior_tree')
    declare_bt_xml_arg = DeclareLaunchArgument(
        'behavior_tree',
        default_value=os.path.join(
            sentor_guard_dir, 'examples', 'nav2_examples', 'navigate_with_guard.xml'),
        description='Full path to behavior tree XML file'
    )
    
    # BT Navigator parameters
    bt_navigator_params = {
        'default_nav_to_pose_bt_xml': behavior_tree_xml,
        'plugin_lib_names': [
            'nav2_compute_path_to_pose_action_bt_node',
            'nav2_follow_path_action_bt_node',
            'nav2_back_up_action_bt_node',
            'nav2_spin_action_bt_node',
            'nav2_wait_action_bt_node',
            'nav2_clear_costmap_service_bt_node',
            'nav2_is_stuck_condition_bt_node',
            'nav2_goal_reached_condition_bt_node',
            'nav2_goal_updated_condition_bt_node',
            'nav2_rate_controller_bt_node',
            'nav2_distance_controller_bt_node',
            'nav2_speed_controller_bt_node',
            'nav2_truncate_path_action_bt_node',
            'nav2_recovery_node_bt_node',
            'nav2_pipeline_sequence_bt_node',
            'nav2_round_robin_node_bt_node',
            'nav2_transform_available_condition_bt_node',
            'nav2_time_expired_condition_bt_node',
            'nav2_distance_traveled_condition_bt_node',
            # Add sentor_guard BT plugin
            'sentor_guard_bt_nodes',
        ]
    }
    
    # BT Navigator node
    bt_navigator_node = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[bt_navigator_params],
    )
    
    # Example: Publish mock state and mode for testing
    # In a real system, these would come from RobotStateMachine
    mock_state_publisher = Node(
        package='sentor_guard',
        executable='python_guard_example.py',
        name='mock_state_publisher',
        output='screen',
        parameters=[
            {'publish_mock_topics': True}
        ]
    )
    
    return LaunchDescription([
        declare_bt_xml_arg,
        bt_navigator_node,
        # mock_state_publisher,  # Uncomment for testing without real state machine
    ])
