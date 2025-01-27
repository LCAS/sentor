from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value='',
            description='Configuration file for sentor'
        ),
        DeclareLaunchArgument(
            'safe_operation_timeout',
            default_value='10.0',
            description='Timeout for safe operation'
        ),
        DeclareLaunchArgument(
            'auto_safety_tagging',
            default_value='true',
            description='Enable automatic safety tagging'
        ),
        DeclareLaunchArgument(
            'safety_pub_rate',
            default_value='10.0',
            description='Safety publishing rate'
        ),
        DeclareLaunchArgument(
            'independent_tags',
            default_value='false',
            description='Use independent tags'
        ),

        Node(
            package='sentor',
            executable='sentor_node.py',
            name='sentor',
            output='screen',
            parameters=[{
                'config_file': LaunchConfiguration('config_file'),
                'safe_operation_timeout': LaunchConfiguration('safe_operation_timeout'),
                'auto_safety_tagging': LaunchConfiguration('auto_safety_tagging'),
                'safety_pub_rate': LaunchConfiguration('safety_pub_rate'),
                'independent_tags': LaunchConfiguration('independent_tags')
            }]
        )
    ])