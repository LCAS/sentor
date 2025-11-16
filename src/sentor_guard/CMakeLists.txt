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

# Include directories
include_directories(include)

# C++ Guard Library
add_library(${PROJECT_NAME} SHARED
  src/guard.cpp
)
ament_target_dependencies(${PROJECT_NAME}
  rclcpp
  std_msgs
)

# C++ Topic Guard Node
add_executable(topic_guard_node
  src/topic_guard_node.cpp
)
ament_target_dependencies(topic_guard_node
  rclcpp
  std_msgs
)
target_link_libraries(topic_guard_node ${PROJECT_NAME})

# C++ Lifecycle Guard Node
add_executable(lifecycle_guard_node
  src/lifecycle_guard_node.cpp
)
ament_target_dependencies(lifecycle_guard_node
  rclcpp
  lifecycle_msgs
  std_msgs
)
target_link_libraries(lifecycle_guard_node ${PROJECT_NAME})

# Install C++ libraries and executables
install(TARGETS
  ${PROJECT_NAME}
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

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  examples/python_guard_example.py
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
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
  
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_python_guard test/test_python_guard.py)
endif()

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME})
ament_export_dependencies(rclcpp std_msgs lifecycle_msgs)

ament_package()
