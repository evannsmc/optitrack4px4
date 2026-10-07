# OptiTrack4PX4
### An OptiTrack → ROS 2 → PX4 External Vision Bridge
![Status](https://img.shields.io/badge/Status-Hardware_Validated-blue)
![OptiTrack](https://img.shields.io/badge/Motive-Client-blue)
[![ROS 2 Humble_Compatible](https://img.shields.io/badge/ROS%202-Humble-blue)](https://docs.ros.org/en/humble/index.html)
[![ROS 2 Jazzy_Compatible](https://img.shields.io/badge/ROS%202-Jazzy-blue)](https://docs.ros.org/en/jazzy/index.html)
[![PX4 Compatible](https://img.shields.io/badge/PX4-Autopilot-pink)](https://github.com/PX4/PX4-Autopilot)
[![evannsmc.com](https://img.shields.io/badge/evannsmc.com-Project%20Page-blue)](https://www.evannsmc.com/projects/mocap4px4)

`optitrack4px4` is a ROS 2 (C++) package that streams OptiTrack motion capture data into the PX4 EKF using External Vision fusion, enabling position and heading fusion for hardware flight experiments. The package connects to OptiTrack's Motive software via the NatNet protocol, converts Y-up ENU measurements to NED, and publishes pose data in quaternions as well as euler angles under the rigid body name as defined in Motive.

Another launch file then relays this information for use in PX4 External Vision EKF Fusion by publishing the data as `px4_msgs/msg/VehicleOdometry` messages on `/fmu/in/vehicle_visual_odometry`, and handles the quaternion reordering and timestamping that PX4 expects. A secondary full-state relay node is available to merge the fused EKF output back from `/fmu/out/vehicle_odometry`, and `/fmu/out/vehicle_local_position` into one topic that relays all pose data including available higher order derivatives from the EKF for convenient logging and control.

Tested with ROS 2 Jazzy Jalisco (Ubuntu 24.04) and Humble Hawksbill (Ubuntu 22.04).

---

## Quick start

Assumes ROS 2 Jazzy or Humble is installed ([guide](https://docs.ros.org/en/jazzy/Installation.html)).

```bash
git clone --recursive https://github.com/evannsmc/optitrack4px4.git ~/ws_optitrack/src
~/ws_optitrack/src/setup.sh
source ~/ws_optitrack/install/setup.bash
```

This repository **is** the workspace's `src/` directory: it holds the `optitrack4px4` package next to its
dependencies, which are git submodules (`px4_msgs` @ `v1.16_minimal_msgs`, `mocap_msgs`,
`mocap_px4_relays`). `setup.sh` fetches the submodules, installs system dependencies with `rosdep`,
and builds everything with `colcon build --symlink-install` in Release mode.

- **Update:** `git -C ~/ws_optitrack/src pull --recurse-submodules && ~/ws_optitrack/src/setup.sh`
- **Rebuild without rosdep:** `setup.sh --no-deps` (any other arguments go to `colcon build`)
- **Existing workspace:** clone into `<ws>/src/optitrack4px4` instead; `setup.sh` detects this. If that workspace
  already has `px4_msgs`, `mocap_msgs` or `mocap_px4_relays`, remove one copy (or `touch <copy>/COLCON_IGNORE`),
  since colcon refuses duplicate package names.
- **Dev container:** open the repo in VS Code and choose *Reopen in Container* (Jazzy by default;
  set `ROS_DISTRO=humble` on the host for Humble).

### Configure your network

Edit `optitrack4px4/config/optitrack4px4_params.yaml`:

```yaml
server_address: "192.168.1.113"   # IP of the PC running Motive
local_address: "192.168.1.200"    # IP of this machine
```

With `--symlink-install` no rebuild is needed. You can also override any parameter at launch
(`server_address:=192.168.1.50 local_address:=192.168.1.20`) or pass your own file with `params_file:=/path/to/params.yaml`.
Both machines must be on the same LAN. The default is **Unicast** on NatNet ports `1510`/`1511`; match these to Motive's Data Streaming settings.

### Launch

```bash
# Client + visual odometry relay (typical flight-test configuration)
ros2 launch optitrack4px4 bringup.launch.py vo_relay:=true

# ... + full state relay
ros2 launch optitrack4px4 bringup.launch.py vo_relay:=true full_state_relay:=true

# Client only
ros2 launch optitrack4px4 bringup.launch.py
```

| Argument | Default | Description |
|----------|---------|-------------|
| `vo_relay` | `false` | Run `visual_odometry_relay` (pose -> `/fmu/in/vehicle_visual_odometry`) |
| `full_state_relay` | `false` | Run `full_state_relay` (PX4 EKF -> `mocap_msgs/FullState`) |
| `params_file` | `config/optitrack4px4_params.yaml` | Client parameters |
| `rigid_body_name` | `drone` | Rigid body (as named in Motive) that the relay forwards to PX4 |
| any [client parameter](#configuration) | from `params_file` | Override a single value |

`ros2 launch optitrack4px4 bringup.launch.py --show-args` lists everything. The previous launch files still work
and are shortcuts for the above: `client.launch.py`, `client_and_visual_odometry.launch.py`
(`vo_relay:=true`) and `client_vision_full_all.launch.py` (both relays).

### Example topic tree (all three nodes running) assuming your rigid body is named `drone` in Motive

```text
/optitrack/
├── drone/
│   ├── drone       [geometry_msgs/PoseStamped]
│   └── drone_euler [mocap_msgs/PoseEuler]

/fmu/in/vehicle_visual_odometry          [px4_msgs/VehicleOdometry]   <- to EKF   (mocap_px4_relays)
/merge_odom_localpos/full_state_relay    [mocap_msgs/FullState]       <- from EKF  (mocap_px4_relays)
```

```bash
# Verify vision data is reaching PX4
ros2 topic echo /fmu/in/vehicle_visual_odometry

# Check the merged full-state output
ros2 topic echo /merge_odom_localpos/full_state_relay

# Raw OptiTrack pose
ros2 topic echo /optitrack/drone/drone
```

#### Published topics of the client.launch.py alone

All topics are published under the configured `namespace` (default `optitrack`). Topics are created dynamically for each rigid body discovered in Motive:

```text
/<namespace>/<rigid_body_name>/<rigid_body_name>         [geometry_msgs/PoseStamped]
/<namespace>/<rigid_body_name>/<rigid_body_name>_euler    [mocap_msgs/PoseEuler]
```

- **PoseStamped**: position (x, y, z) + quaternion (qw, qx, qy, qz) in NED
- **PoseEuler**: position (x, y, z) + roll, pitch, yaw in radians

`<rigid_body_name>` is taken from the rigid body definitions in Motive.

#### TF tree

```text
map (world_frame)
└── optitrack (optitrack_frame)          [static]
    ├── <rigid_body_1>_<rigid_body_1>    [dynamic]
    └── <rigid_body_2>_<rigid_body_2>    [dynamic]
```

The static `map -> optitrack` transform is defined by `map_xyz` and `map_rpy`. Dynamic child frames update with each OptiTrack measurement.

---

## Relay nodes

The **visual_odometry_relay** and **full_state_relay** nodes have been moved to the [`mocap_px4_relays`](mocap_px4_relays/) package so they can be reused with any motion capture source (Vicon, OptiTrack, etc.). See that package's README for full documentation.

### Data pipeline

```text
OptiTrack Motive (Y-up ENU, millimeters)
        |
   optitrack_client node  (optitrack4px4)
        |  connects via NatNet (Unicast/Multicast)
        |  converts Y-up ENU -> NED, mm -> m
        v
  /optitrack/*rigid_body_name*/*rigid_body_name* (geometry_msgs/PoseStamped, NED)
        |
  visual_odometry_relay node  (mocap_px4_relays)
        |  reorders quaternion, stamps, publishes at 35 Hz
        v
  /fmu/in/vehicle_visual_odometry  (px4_msgs/VehicleOdometry)
        |
   PX4 EKF2 (fuses vision + IMU)
        |
        v
  /fmu/out/vehicle_odometry & /fmu/out/vehicle_local_position
        |
  full_state_relay node  (mocap_px4_relays)  [optional]
        |  merges both into one topic at 40 Hz
        v
  /merge_odom_localpos/full_state_relay  (mocap_msgs/FullState)
```

For the EKF to accept vision input you must enable it on the PX4 side (the `EKF2_EV_CTRL` and `EKF2_HGT_REF` must be set up according to what your motion capture system can provide). It is also recommended to turn off magnetometer fusion to avoid issues in indoor environments.

---

## Configuration

Parameters of `optitrack_client`, read from `optitrack4px4/config/optitrack4px4_params.yaml` (or `params_file:=`). Each one can be overridden as a launch argument of the same name, except `namespace`, whose launch argument is `topic_namespace`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `connection_type` | `Unicast` | `Unicast` or `Multicast` |
| `server_address` | `192.168.1.113` | IP of the machine running Motive |
| `local_address` | `192.168.1.200` | IP of this machine |
| `multicast_address` | `239.255.42.99` | Multicast group (Multicast mode only) |
| `server_command_port` | `1510` | NatNet command port |
| `server_data_port` | `1511` | NatNet data port |
| `namespace` | `optitrack` | Topic namespace prefix |
| `world_frame` | `map` | Global TF reference frame |
| `optitrack_frame` | `optitrack` | OptiTrack TF reference frame |
| `map_xyz` | `[0.0, 0.0, 0.0]` | Static translation: world_frame -> optitrack_frame (meters) |
| `map_rpy` | `[0.0, 0.0, 0.0]` | Static rotation: world_frame -> optitrack_frame |
| `map_rpy_in_degrees` | `false` | If `true`, `map_rpy` values are in degrees |

---

## Requirements

- [OptiTrack Motive](https://optitrack.com/software/motive/) running on another machine, with NatNet streaming enabled and reachable over the network
- ROS 2 Jazzy Jalisco or Humble Hawksbill installed and sourced (at least *ros-jazzy-ros-base* and *ros-dev-tools* packages, [installation guide](https://docs.ros.org/en/jazzy/Installation.html))
- *rosdep* for ROS 2 package dependencies (`setup.sh` initializes it on first run; [guide](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Rosdep.html))
- [`px4_msgs`](https://github.com/evannsmc/px4_msgs/tree/v1.16_minimal_msgs), [`mocap_msgs`](https://github.com/evannsmc/mocap_msgs) and [`mocap_px4_relays`](https://github.com/evannsmc/mocap_px4_relays) are included as git submodules

> Note: the NatNet SDK is vendored inside this repository; no system-wide NatNet install is needed.

---

## Compatibility

- **ROS 2**: Jazzy Jalisco and Humble Hawksbill
- **OS / arch**: Ubuntu 24.04 and 22.04; `x86_64` tested
- **OptiTrack stack**: Motive with NatNet streaming; NatNet SDK **1.12** (vendored)

---

## Repository layout

```text
optitrack4px4/                          # the repo = your workspace's src/
├── setup.sh                     # submodules + rosdep + colcon build
├── .devcontainer/               # VS Code dev container (Jazzy/Humble)
├── .github/workflows/build.yml  # CI: builds on Humble and Jazzy
├── docs/
├── optitrack4px4/                    # the ROS 2 package
│   ├── src/                     # optitrack_client node (communicator, publisher, utils)
│   ├── include/optitrack4px4/
│   ├── launch/
│   │   ├── bringup.launch.py    # client + optional relays (vo_relay:=, full_state_relay:=)
│   │   └── client*.launch.py    # shortcuts for bringup.launch.py
│   ├── config/optitrack4px4_params.yaml
│   ├── NatNetSDK/                  # vendored NatNet SDK 1.12 (headers + libNatNet.so)
├── px4_msgs/                    # submodule (v1.16_minimal_msgs)
├── mocap_msgs/                  # submodule
└── mocap_px4_relays/            # submodule: visual_odometry_relay, full_state_relay
```

---

## Building & linking details

- The package is C++17 and uses `ament_cmake`.
- The **NatNet SDK (1.12)** is vendored in `NatNetSDK/` and linked directly, so you don't need a system-wide installation.
- **Eigen3** is required for quaternion math and is installed via rosdep.
- The install step ships `libNatNet.so` and sets RPATH so that runtime lookups succeed without extra `LD_LIBRARY_PATH` setup.

## Troubleshooting / FAQ

**EKF not fusing vision data**: Ensure `EKF2_EV_CTRL` is set to enable position and/or yaw fusion from external vision. Check that `/fmu/in/vehicle_visual_odometry` is being published at the expected rate with `ros2 topic hz`.

**The node can't connect to OptiTrack/Motive**: verify `server_address`, `local_address`, and network reachability (ping); check that Motive is running and NatNet streaming is enabled in Motive's Data Streaming settings. Confirm the command port (`1510`) and data port (`1511`) match Motive's configuration.

**Frames look misaligned**: adjust `map_xyz` / `map_rpy` and confirm radians vs degrees via `map_rpy_in_degrees`.

**Full state relay not publishing**: the gating requires both `/fmu/out/vehicle_odometry` and `/fmu/out/vehicle_local_position` to arrive at >= 50 Hz. Confirm PX4 is running and the DDS/uXRCE bridge is healthy.

**I don't see TF in RViz**: confirm TF display is enabled and the fixed frame matches your global frame (`world_frame`/`optitrack_frame`).

---

### Frames & mapping

- The OptiTrack frame -> world frame mapping is configurable via `world_frame`, `optitrack_frame`, `map_xyz` and `map_rpy`.
- `map_rpy_in_degrees` lets you specify rotations in degrees when convenient.
- Frame IDs for rigid bodies are derived from the names defined in Motive.

> Units follow ROS conventions (positions in meters, rotations in radians) in downstream consumers; ensure your system uses consistent units end-to-end.

---

## Website

This project is part of the [evannsmc open-source portfolio](https://www.evannsmc.com/projects).

- [Project page](https://www.evannsmc.com/projects/mocap4px4)

## License & attribution

- **License:** GNU General Public License v3.0 (GPL-3.0)
