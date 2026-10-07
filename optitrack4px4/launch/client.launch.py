"""OptiTrack client only. Kept for backward compatibility; see bringup.launch.py."""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    bringup = get_package_share_directory('optitrack4px4') + '/launch/bringup.launch.py'
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup),
            launch_arguments={'vo_relay': 'false', 'full_state_relay': 'false'}.items(),
        ),
    ])
