#!/usr/bin/env bash
# One-shot setup: fetch submodules, install ROS deps with rosdep, build with colcon.
#
#   ./src/setup.sh                  # from the workspace root (repo cloned as <ws>/src)
#   ./setup.sh --no-deps            # skip rosdep (e.g. offline rebuild)
#   ./setup.sh --packages-up-to X   # any other args are passed to `colcon build`
#
# The workspace root is the parent of this repo, or its grandparent if the repo
# was cloned into an existing <ws>/src/<name>. Override with WS_DIR=/path.
set -eo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${WS_DIR:-}" ]]; then
  if [[ "$(basename "$(dirname "$REPO_DIR")")" == "src" ]]; then
    WS_DIR="$(dirname "$(dirname "$REPO_DIR")")"
  else
    WS_DIR="$(dirname "$REPO_DIR")"
  fi
fi

INSTALL_DEPS=1
COLCON_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --no-deps) INSTALL_DEPS=0 ;;
    -h|--help) sed -n '2,9p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) COLCON_ARGS+=("$arg") ;;
  esac
done

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# --- ROS 2 environment -------------------------------------------------------
if [[ -z "${AMENT_PREFIX_PATH:-}" ]]; then
  for distro in ${ROS_DISTRO:-} jazzy humble; do
    if [[ -f "/opt/ros/$distro/setup.bash" ]]; then
      source "/opt/ros/$distro/setup.bash"
      break
    fi
  done
fi
if [[ -z "${ROS_DISTRO:-}" ]]; then
  echo "ROS 2 not found. Install Jazzy or Humble, or source your ROS 2 setup.bash first." >&2
  exit 1
fi
echo "ROS 2 $ROS_DISTRO | workspace: $WS_DIR"

# --- Submodules (px4_msgs, mocap_msgs, mocap_px4_relays) ---------------------
step "Fetching submodules"
git -C "$REPO_DIR" submodule update --init --recursive

# --- System dependencies -----------------------------------------------------
if [[ "$INSTALL_DEPS" == 1 ]]; then
  step "Installing dependencies with rosdep"
  if [[ ! -d /etc/ros/rosdep/sources.list.d ]]; then
    echo "rosdep is not initialized; running 'sudo rosdep init'"
    sudo rosdep init
  fi
  if [[ ! -d "$HOME/.ros/rosdep/sources.cache" ]]; then
    rosdep update --rosdistro "$ROS_DISTRO"
  fi
  rosdep install --from-paths "$REPO_DIR" --ignore-src --rosdistro "$ROS_DISTRO" -y
fi

# --- Build -------------------------------------------------------------------
step "Building with colcon"
cd "$WS_DIR"
python3 -m colcon build \
  --symlink-install \
  "${COLCON_ARGS[@]}" \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

step "Done. In every new terminal run:"
echo "  source $WS_DIR/install/setup.bash"
