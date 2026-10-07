"""Bring up the OptiTrack client and, optionally, the PX4 relays.

Defaults come from config/optitrack4px4_params.yaml (or `params_file:=...`).
Any client parameter can be overridden on the command line; arguments left
empty fall back to the params file.

    ros2 launch optitrack4px4 bringup.launch.py                        # client only
    ros2 launch optitrack4px4 bringup.launch.py vo_relay:=true         # + vision -> PX4
    ros2 launch optitrack4px4 bringup.launch.py vo_relay:=true full_state_relay:=true
"""
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

PACKAGE = 'optitrack4px4'
NODE_NAME = 'optitrack_client'

# launch argument -> (node parameter, type, description)
CLIENT_ARGS = {
    'connection_type': ('connection_type', str, 'Unicast or Multicast'),
    'server_address': ('server_address', str, 'OptiTrack/Motive server IP address'),
    'local_address': ('local_address', str, 'Local machine IP address'),
    'multicast_address': ('multicast_address', str, 'Multicast group address (Multicast mode only)'),
    'server_command_port': ('server_command_port', int, 'NatNet command port'),
    'server_data_port': ('server_data_port', int, 'NatNet data port'),
    'topic_namespace': ('namespace', str, 'Topic namespace for OptiTrack messages'),
    'world_frame': ('world_frame', str, 'World frame for tf2 transformations'),
    'optitrack_frame': ('optitrack_frame', str, 'OptiTrack frame for tf2 transformations'),
    'map_xyz': ('map_xyz', list, 'XYZ translation world_frame -> optitrack_frame'),
    'map_rpy': ('map_rpy', list, 'RPY rotation world_frame -> optitrack_frame'),
    'map_rpy_in_degrees': ('map_rpy_in_degrees', bool, 'Whether map_rpy is in degrees'),
}


def _parse(value, kind):
    if kind is str:
        return value
    parsed = yaml.safe_load(value)
    if kind is list:
        return [float(v) for v in parsed]
    return kind(parsed)


def _launch_setup(context):
    params_file = LaunchConfiguration('params_file').perform(context)
    with open(params_file) as f:
        file_params = yaml.safe_load(f)[NODE_NAME]['ros__parameters']

    overrides = {}
    for arg, (param, kind, _) in CLIENT_ARGS.items():
        value = LaunchConfiguration(arg).perform(context)
        if value != '':
            overrides[param] = _parse(value, kind)

    namespace = overrides.get('namespace', file_params['namespace'])
    rigid_body_name = LaunchConfiguration('rigid_body_name').perform(context)

    return [
        Node(
            package=PACKAGE,
            executable=NODE_NAME,
            output='screen',
            parameters=[params_file, overrides],
        ),
        # The relay subscribes to a hardcoded /vicon/drone/drone; point it at
        # /{namespace}/{rigid_body_name}/{rigid_body_name} instead.
        Node(
            package='mocap_px4_relays',
            executable='visual_odometry_relay',
            output='screen',
            remappings=[
                ('/vicon/drone/drone',
                 f'/{namespace}/{rigid_body_name}/{rigid_body_name}'),
            ],
            condition=IfCondition(LaunchConfiguration('vo_relay')),
        ),
        Node(
            package='mocap_px4_relays',
            executable='full_state_relay',
            output='screen',
            condition=IfCondition(LaunchConfiguration('full_state_relay')),
        ),
    ]


def generate_launch_description():
    default_params = os.path.join(
        get_package_share_directory(PACKAGE), 'config', f'{PACKAGE}_params.yaml')

    args = [
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='YAML file with optitrack_client parameters'),
        DeclareLaunchArgument('vo_relay', default_value='false',
                              description='Also run visual_odometry_relay (pose -> PX4 EKF)'),
        DeclareLaunchArgument('full_state_relay', default_value='false',
                              description='Also run full_state_relay (PX4 EKF -> FullState)'),
        DeclareLaunchArgument('rigid_body_name', default_value='drone',
                              description='Rigid body (as named in Motive) to relay to PX4'),
    ]
    args += [
        DeclareLaunchArgument(arg, default_value='',
                              description=f'{desc} (empty: use params_file)')
        for arg, (_, _, desc) in CLIENT_ARGS.items()
    ]

    return LaunchDescription(args + [OpaqueFunction(function=_launch_setup)])
