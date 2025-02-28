from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterFile
from launch_ros.substitutions import FindPackageShare

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    AndSubstitution,
    LaunchConfiguration,
    NotSubstitution,
    PathJoinSubstitution,
)

from moveit_configs_utils import MoveItConfigsBuilder

def launch_setup(context, *args, **kwargs):
    # Arguments passed to the robot description XACRO
    fake_ur = LaunchConfiguration("fake_ur")
    fake_gripper = LaunchConfiguration("fake_gripper")
    ur_type = LaunchConfiguration("ur_type")
    robot_name = LaunchConfiguration("robot_name")
    tf_prefix = LaunchConfiguration("tf_prefix")
    robot_ip = LaunchConfiguration("robot_ip")
    tool_device_name = LaunchConfiguration("tool_device_name")
    use_tool_communication = LaunchConfiguration("use_tool_communication")
    tool_tcp_port = LaunchConfiguration("tool_tcp_port")
    headless_mode = LaunchConfiguration("headless_mode")
    robotiq_use_socket_communication = LaunchConfiguration("robotiq_use_socket_communication")
    robotiq_ip_address = LaunchConfiguration("robotiq_ip_address")
    robotiq_port = LaunchConfiguration("robotiq_port")
    robotiq_connection_timeout = LaunchConfiguration("robotiq_connection_timeout")
    robotiq_activate_gripper_by_default = LaunchConfiguration("robotiq_activate_gripper_by_default")

    # Arguments passed just to the nodes
    runtime_config_package = LaunchConfiguration("runtime_config_package")
    controllers_file = LaunchConfiguration("controllers_file")
    description_package = LaunchConfiguration("description_package")
    description_file = LaunchConfiguration("description_file")
    controller_spawner_timeout = LaunchConfiguration("controller_spawner_timeout")
    activate_joint_controller = LaunchConfiguration("activate_joint_controller")
    initial_joint_controller = LaunchConfiguration("initial_joint_controller")
    launch_rviz = LaunchConfiguration("launch_rviz")
    launch_dashboard_client = LaunchConfiguration("launch_dashboard_client")

    srdf_path = PathJoinSubstitution([FindPackageShare('ur_robotiq_moveit_config'), 'config', 'ur_robotiq.srdf']).perform(context)
    joint_limits_path = PathJoinSubstitution([FindPackageShare('ur_robotiq_moveit_config'), 'config', 'joint_limits.yaml']).perform(context)
    moveit_controllers_path = PathJoinSubstitution([FindPackageShare('ur_robotiq_bringup'), 'config', 'moveit_controllers.yaml']).perform(context)
    pilz_limits_path = PathJoinSubstitution([FindPackageShare('ur_robotiq_moveit_config'), 'config', 'pilz_cartesian_limits.yaml']).perform(context)

    moveit_config = (
        MoveItConfigsBuilder('ur_robotiq', package_name='ur_robotiq_moveit_config')
        .robot_description(file_path=PathJoinSubstitution([FindPackageShare(description_package), "urdf", description_file]).perform(context),
                            mappings= {"fake_ur": fake_ur,
                                       "fake_gripper": fake_gripper, 
                                       "ur_type": ur_type, 
                                       "robot_name": robot_name, 
                                       "tf_prefix": tf_prefix, 
                                       "robot_ip": robot_ip, 
                                       "tool_device_name": tool_device_name, 
                                       "use_tool_communication": use_tool_communication, 
                                       "tool_tcp_port": tool_tcp_port, 
                                       "headless_mode": headless_mode,
                                       "robotiq_use_socket_communication": robotiq_use_socket_communication,
                                       "robotiq_ip_address": robotiq_ip_address,
                                       "robotiq_port": robotiq_port,
                                       "robotiq_connection_timeout": robotiq_connection_timeout,
                                       "robotiq_activate_gripper_by_default": robotiq_activate_gripper_by_default,})
        .robot_description_semantic(file_path=srdf_path)
        .planning_scene_monitor(publish_robot_description=False,
                                publish_robot_description_semantic=True,
                                publish_planning_scene=True)
        .planning_pipelines(default_planning_pipeline='ompl', pipelines=['ompl', 'chomp', 'pilz_industrial_motion_planner'])
        .pilz_cartesian_limits(file_path=pilz_limits_path)
        .joint_limits(file_path=joint_limits_path)
        .trajectory_execution(file_path=moveit_controllers_path)
        .robot_description_kinematics()
        .to_moveit_configs()
    )

    robot_description = moveit_config.robot_description

    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[
            moveit_config.to_dict(),
            # {"move_group": {"planning_plugin": "ompl_interface/OMPLPlanner"}},
        ],
    )

    initial_joint_controllers = PathJoinSubstitution(
        [FindPackageShare(runtime_config_package), "config", controllers_file]
    )

    rviz_config_file = PathJoinSubstitution(
        [FindPackageShare(description_package), "config", "view_cell.rviz"]
    )

    # Define update rate for UR Robot
    update_rate_config_file = PathJoinSubstitution(
        [
            FindPackageShare(runtime_config_package),
            "config",
            ur_type.perform(context) + "_update_rate.yaml",
        ]
    )

    # Define if condition for both UR Robot and Robotiq Gripper fake hardware (AND)
    fake_ur_and_gripper = AndSubstitution(fake_ur, fake_gripper)

    # UR Robot nodes
    control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[
            robot_description,
            update_rate_config_file,
            ParameterFile(initial_joint_controllers, allow_substs=True),
        ],
        output="screen",
        condition=IfCondition(fake_ur_and_gripper),
    )

    ur_control_node = Node(
        package="ur_robot_driver",
        executable="ur_ros2_control_node",
        parameters=[
            robot_description,
            update_rate_config_file,
            ParameterFile(initial_joint_controllers, allow_substs=True),
        ],
        output="screen",
        condition=UnlessCondition(fake_ur),
    )

    dashboard_client_node = Node(
        package="ur_robot_driver",
        condition=IfCondition(
            AndSubstitution(launch_dashboard_client, NotSubstitution(fake_ur))
        ),
        executable="dashboard_client",
        name="dashboard_client",
        output="screen",
        emulate_tty=True,
        parameters=[{"robot_ip": robot_ip}],
    )

    tool_communication_node = Node(
        package="ur_robot_driver",
        condition=IfCondition(use_tool_communication),
        executable="tool_communication.py",
        name="ur_tool_comm",
        output="screen",
        parameters=[
            {
                "robot_ip": robot_ip,
                "tcp_port": tool_tcp_port,
                "device_name": tool_device_name,
            }
        ],
    )

    urscript_interface = Node(
        package="ur_robot_driver",
        executable="urscript_interface",
        parameters=[{"robot_ip": robot_ip}],
        output="screen",
    )

    controller_stopper_node = Node(
        package="ur_robot_driver",
        executable="controller_stopper_node",
        name="controller_stopper",
        output="screen",
        emulate_tty=True,
        condition=UnlessCondition(fake_ur),
        parameters=[
            {"headless_mode": headless_mode},
            {"joint_controller_active": activate_joint_controller},
            {
                "consistent_controllers": [
                    "io_and_status_controller",
                    "force_torque_sensor_broadcaster",
                    "joint_state_broadcaster",
                    "speed_scaling_state_broadcaster",
                    "ur_configuration_controller",
                ]
            },
        ],
    )

    # RSP and Rviz nodes
    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        parameters=[robot_description],
    )

    rviz_node = TimerAction(
        period=5.0,  # Delay in seconds
        actions=[
            Node(
                package="rviz2",
                condition=IfCondition(launch_rviz),
                executable="rviz2",
                name="rviz2",
                output="log",
                arguments=["-d", rviz_config_file],
                parameters=[
                    moveit_config.robot_description,
                    moveit_config.robot_description_semantic,
                    moveit_config.planning_pipelines,
                    moveit_config.robot_description_kinematics,
                ],
            ),
        ]
    )

    # Spawn controllers
    def controller_spawner(controllers, active=True):
        inactive_flags = ["--inactive"] if not active else []
        return Node(
            package="controller_manager",
            executable="spawner",
            arguments=[
                "--controller-manager",
                "/controller_manager",
                "--controller-manager-timeout",
                controller_spawner_timeout,
            ]
            + inactive_flags
            + controllers,
        )

    controllers_active = [ # scaled_joint_trajectory_controller is loaded and activated by default
        "joint_state_broadcaster",
        "io_and_status_controller",
        "speed_scaling_state_broadcaster",
        "force_torque_sensor_broadcaster",
        "ur_configuration_controller",
        "robotiq_activation_controller",
    ]
    controllers_inactive = [
        "forward_position_controller",
        "joint_trajectory_controller",
        "robotiq_action_controller",
        "robotiq_forward_command_controller",
    ]

    controller_spawners = [controller_spawner(controllers_active)] + [
        controller_spawner(controllers_inactive, active=False)
    ]

    # There may be other controllers of the joints, but this is the initially-started one
    initial_joint_controller_spawner_started = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            initial_joint_controller,
            "-c",
            "/controller_manager",
            "--controller-manager-timeout",
            controller_spawner_timeout,
        ],
        condition=IfCondition(activate_joint_controller),
    )
    initial_joint_controller_spawner_stopped = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            initial_joint_controller,
            "-c",
            "/controller_manager",
            "--controller-manager-timeout",
            controller_spawner_timeout,
            "--inactive",
        ],
        condition=UnlessCondition(activate_joint_controller),
    )

    nodes_to_start = [
        move_group_node,
        control_node,
        ur_control_node,
        dashboard_client_node,
        tool_communication_node,
        controller_stopper_node,
        urscript_interface,
        robot_state_publisher_node,
        rviz_node,
        initial_joint_controller_spawner_stopped,
        initial_joint_controller_spawner_started,
    ] + controller_spawners

    return nodes_to_start


def generate_launch_description():
    declared_arguments = []

    declared_arguments.append(
        DeclareLaunchArgument(
            "fake_ur",
            description="[MANDATORY ARG] Start robot with fake hardware mirroring command to its states.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "fake_gripper",
            description="[MANDATORY ARG] Start gripper with fake hardware mirroring command to its states.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "ur_type",
            default_value="ur10e",
            description="Type/series of used UR robot.",
            choices=["ur3", "ur3e", "ur5", "ur5e", "ur10", "ur10e", "ur16e", "ur20", "ur30"],
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "robot_name",
            default_value="ur10e",
            description="Name of the robot.",
            choices=["ur3", "ur3e", "ur5", "ur5e", "ur10", "ur10e", "ur16e", "ur20", "ur30"],
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tf_prefix",
            default_value="ur10e_",
            description="tf_prefix of the joint names, useful for "
            "multi-robot setup. If changed, also joint names in the controllers' configuration "
            "have to be updated.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "robot_ip",
            default_value="192.168.10.2",
            description="IP address by which the robot can be reached.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_device_name",
            default_value= "/tmp/ttyUR", #"/home/nyquist/ttyUR", # 
            description="File descriptor that will be generated for the tool communication device. "
            "The user has be be allowed to write to this location. "
            "Only effective, if use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "use_tool_communication",
            default_value="false", #"true",
            description="Only available for e series!",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "tool_tcp_port",
            default_value="54321",
            description="Remote port that will be used for bridging the tool's serial device. "
            "Only effective, if use_tool_communication is set to True.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "headless_mode",
            default_value="true",
            description="Enable headless mode for robot control",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "robotiq_use_socket_communication",
            description="[MANDATORY ARG] Use socket communication for Robotiq Gripper?",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            name="robotiq_ip_address",
            default_value="192.168.10.2",
            description="Ip address for socket communication",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            name="robotiq_port",
            default_value="63352",
            description="Port for socket communication",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            name="robotiq_connection_timeout",
            default_value="30000",
            description="Connection timeout for socket communication",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            name="robotiq_activate_gripper_by_default",
            default_value="0",
            description="Activate gripper by default?",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "runtime_config_package",
            default_value="ur_robotiq_bringup",
            description='Package with the controller\'s configuration in "config" folder. '
            "Usually the argument is not set, it enables use of a custom setup.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "controllers_file",
            default_value="ros2_controllers.yaml",
            description="YAML file with the controllers configuration.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "description_package",
            default_value="ur_robotiq_description",
            description="Description package with robot URDF/XACRO files. Usually the argument "
            "is not set, it enables use of a custom description.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "description_file",
            default_value="ur_robotiq.urdf.xacro",
            description="URDF/XACRO description file with the robot.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "controller_spawner_timeout",
            default_value="100",
            description="Timeout used when spawning controllers.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "activate_joint_controller",
            default_value="true",
            description="Activate loaded joint controller.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "initial_joint_controller",
            default_value="scaled_joint_trajectory_controller",
            description="Initially loaded robot controller.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "launch_rviz",
            default_value="true",
            description="Launch RViz?",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "launch_dashboard_client",
            default_value="true",
            description="Launch Dashboard Client?"
        )
    )
    
    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)])
