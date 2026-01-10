cmake_minimum_required(VERSION 3.8)
project(timeos_msgs)

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
