from launch import LaunchDescription, LaunchContext
from launch.actions import OpaqueFunction, DeclareLaunchArgument
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
from launch.conditions import IfCondition
import os


def total_launcher(context: LaunchContext, *args, **kwargs):
    ns_sub = context.perform_substitution(LaunchConfiguration('ns'))
    ns_str = "{}".format(ns_sub)

    rviz_file = os.path.join(get_package_share_directory('ur_robotiq_description'), 'config',
                             "view_cell.rviz")

    rviz_node = Node(package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['--display-config', rviz_file],
        condition=IfCondition(LaunchConfiguration('rviz'))
        )

    node = namespace_nodes(ns_str)

    return node + [rviz_node]


def namespace_nodes(ns_str):
    joint_state_publisher_node = Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            # namespace=ns_str,
            condition=IfCondition(LaunchConfiguration('js_publisher_gui'))
        )

    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name='xacro')]),
            ' ',
            PathJoinSubstitution([FindPackageShare('ur_robotiq_description'), "urdf", 'ur_robotiq.urdf.xacro']),
            
        ]
    )

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description_content}],
        )
    return [robot_state_publisher_node, joint_state_publisher_node]


def generate_launch_description():

    ns_launch_arg = DeclareLaunchArgument(
        name='ns',
        default_value='',
        description='Namespace'
    )

    rviz_launch_arg = DeclareLaunchArgument(
        name='rviz',
        default_value='True',
        description='Launch rviz'
    )

    gui_launch_arg = DeclareLaunchArgument(
        name='js_publisher_gui',
        default_value='True',
        description='Launch joint_state_publisher_gui'
    )

    nodes_to_start = [
        ns_launch_arg,
        rviz_launch_arg,
        gui_launch_arg,
        OpaqueFunction(function=total_launcher, args=[]),
    ]
    
    return LaunchDescription(nodes_to_start)