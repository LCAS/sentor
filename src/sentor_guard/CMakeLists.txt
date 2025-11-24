cmake_minimum_required(VERSION 3.8)
project(sentor_guard)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(lifecycle_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Optional: BehaviorTree.CPP for Nav2 integration
find_package(behaviortree_cpp QUIET)
if(behaviortree_cpp_FOUND)
  message(STATUS "BehaviorTree.CPP found - building BT plugin")
  set(BUILD_BT_PLUGIN TRUE)
else()
  message(STATUS "BehaviorTree.CPP not found - skipping BT plugin")
  set(BUILD_BT_PLUGIN FALSE)
endif()

# Generate ROS messages
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/GuardStatus.msg"
  DEPENDENCIES builtin_interfaces
)

# Include directories
include_directories(include)

# C++ Guard Library
add_library(${PROJECT_NAME}_lib SHARED
  src/guard.cpp
)
ament_target_dependencies(${PROJECT_NAME}_lib
  rclcpp
  std_msgs
)
rosidl_get_typesupport_target(cpp_typesupport_target ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(${PROJECT_NAME}_lib "${cpp_typesupport_target}")

# C++ Topic Guard Node
add_executable(topic_guard_node
  src/topic_guard_node.cpp
)
ament_target_dependencies(topic_guard_node
  rclcpp
  std_msgs
)
target_link_libraries(topic_guard_node ${PROJECT_NAME}_lib)

# C++ Lifecycle Guard Node
add_executable(lifecycle_guard_node
  src/lifecycle_guard_node.cpp
)
ament_target_dependencies(lifecycle_guard_node
  rclcpp
  lifecycle_msgs
  std_msgs
)
target_link_libraries(lifecycle_guard_node ${PROJECT_NAME}_lib)

# BehaviorTree.CPP Plugin for Nav2 integration
if(BUILD_BT_PLUGIN)
  add_library(sentor_guard_bt_nodes SHARED
    src/bt_condition_node.cpp
  )
  ament_target_dependencies(sentor_guard_bt_nodes
    rclcpp
    std_msgs
    behaviortree_cpp
  )
  target_link_libraries(sentor_guard_bt_nodes ${PROJECT_NAME}_lib)
  
  # Install BT plugin library
  install(TARGETS sentor_guard_bt_nodes
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
  )
  
  # Install BT plugin description
  install(FILES sentor_guard_bt_nodes.xml
    DESTINATION share/${PROJECT_NAME}
  )
endif()

# Install C++ libraries and executables
install(TARGETS
  ${PROJECT_NAME}_lib
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(TARGETS
  topic_guard_node
  lifecycle_guard_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

# Install Python modules (handled by setup.py via ament_cmake_python)
# Note: ament_python_install_package is not needed when setup.py exists

# Install Python executables
install(PROGRAMS
  examples/python_guard_example.py
  examples/nav2_examples/test_bt_integration.py
  examples/nav2_examples/simple_guard_demo.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

# Install config files
install(DIRECTORY
  config
  DESTINATION share/${PROJECT_NAME}
)

# Install examples
install(DIRECTORY
  examples
  DESTINATION share/${PROJECT_NAME}
  PATTERN "*.pyc" EXCLUDE
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  #ament_lint_auto_find_test_dependencies()
  
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_python_guard test/test_python_guard.py)
  
  # C++ tests for BT condition node (only if BT.CPP is available)
  if(BUILD_BT_PLUGIN)
    find_package(ament_cmake_gtest REQUIRED)
    ament_add_gtest(test_bt_condition_node test/test_bt_condition_node.cpp)
    target_link_libraries(test_bt_condition_node sentor_guard_bt_nodes)
    ament_target_dependencies(test_bt_condition_node
      rclcpp
      std_msgs
      behaviortree_cpp
    )
  endif()
endif()

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME}_lib)
ament_export_dependencies(
  rosidl_default_runtime
  rclcpp
  std_msgs
  lifecycle_msgs
  builtin_interfaces
)

if(BUILD_BT_PLUGIN)
  ament_export_libraries(sentor_guard_bt_nodes)
  ament_export_dependencies(behaviortree_cpp)
endif()

ament_package()
