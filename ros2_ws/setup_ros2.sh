#!/bin/bash
# TimeOS ROS2 Environment Setup
#
# Usage: source setup_ros2.sh
#
# This script activates the timeos-ros conda environment and
# sources the ROS2 workspace.

# Activate conda environment
if [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
elif [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
else
    echo "Error: conda not found"
    return 1
fi

conda activate timeos-ros

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source ROS2 workspace if built
if [ -f "$SCRIPT_DIR/install/setup.bash" ]; then
    source "$SCRIPT_DIR/install/setup.bash"
    echo "TimeOS ROS2 environment ready"
    echo ""
    echo "Available launch files:"
    echo "  ros2 launch timeos_ros minimal.launch.py"
    echo "  ros2 launch timeos_ros t_symmetry_experiment.launch.py"
    echo ""
    echo "Build with: colcon build"
else
    echo "ROS2 workspace not built. Run:"
    echo "  cd $SCRIPT_DIR && colcon build"
fi
