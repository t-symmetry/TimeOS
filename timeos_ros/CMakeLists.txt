cmake_minimum_required(VERSION 3.8)
project(timeos_ros)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(timeos_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Generate services
rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/CreateEvent.srv"
  "srv/QueryTimeline.srv"
  "srv/PlanDisplacement.srv"
  "srv/ValidateCausality.srv"
  "srv/SetField.srv"
  "srv/GetStatus.srv"
  DEPENDENCIES std_msgs timeos_msgs
)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  timeos_ros/nodes/timeline_node.py
  timeos_ros/nodes/field_generator_node.py
  timeos_ros/nodes/tdu_node.py
  timeos_ros/nodes/causality_monitor_node.py
  timeos_ros/nodes/safety_monitor_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY
  launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
