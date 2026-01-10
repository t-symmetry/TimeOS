cmake_minimum_required(VERSION 3.14)
project(timeos_msgs)

# Suppress CMP0148 warning for deprecated Python modules
if(POLICY CMP0148)
  cmake_policy(SET CMP0148 OLD)
endif()

# Help CMake find Python in conda environment
if(DEFINED ENV{CONDA_PREFIX})
  set(Python3_ROOT_DIR $ENV{CONDA_PREFIX})
  set(Python_ROOT_DIR $ENV{CONDA_PREFIX})
  set(Python3_EXECUTABLE "$ENV{CONDA_PREFIX}/bin/python")
  set(Python_EXECUTABLE "$ENV{CONDA_PREFIX}/bin/python")
  set(PYTHON_EXECUTABLE "$ENV{CONDA_PREFIX}/bin/python")
  set(Python3_INCLUDE_DIR "$ENV{CONDA_PREFIX}/include/python3.11")
  set(Python3_LIBRARY "$ENV{CONDA_PREFIX}/lib/libpython3.11.so")
  set(Python3_NumPy_INCLUDE_DIR "$ENV{CONDA_PREFIX}/lib/python3.11/site-packages/numpy/core/include")
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)

# Message files
set(msg_files
  "msg/ChronoStamp.msg"
  "msg/TemporalFrame.msg"
  "msg/TimelineEvent.msg"
  "msg/CausalityStatus.msg"
  "msg/FieldState.msg"
  "msg/ThermalState.msg"
  "msg/SafetyState.msg"
  "msg/SystemStatus.msg"
  "msg/DisplacementState.msg"
  "msg/AnchorState.msg"
  "msg/SensorReading.msg"
  "msg/ExperimentConfig.msg"
  "msg/MeasurementResult.msg"
)

# Service files
set(srv_files
  "srv/CreateEvent.srv"
  "srv/QueryTimeline.srv"
  "srv/ValidateCausality.srv"
  "srv/SetField.srv"
  "srv/GetSystemStatus.srv"
  "srv/ArmSystem.srv"
  "srv/TriggerEstop.srv"
  "srv/StartExperiment.srv"
  "srv/StopExperiment.srv"
  "srv/SetAnchor.srv"
  "srv/GetMeasurement.srv"
)

# Action files
set(action_files
  "action/Displace.action"
  "action/RampField.action"
  "action/RunExperiment.action"
  "action/Calibrate.action"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  ${action_files}
  DEPENDENCIES std_msgs geometry_msgs sensor_msgs builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
