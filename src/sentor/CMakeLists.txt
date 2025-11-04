cmake_minimum_required(VERSION 3.5)
project(sentor)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(sentor_msgs REQUIRED)

# Install Python package
ament_python_install_package(${PROJECT_NAME})

# Install scripts
install(PROGRAMS
  scripts/sentor_node.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install config files
install(DIRECTORY config
  DESTINATION share/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
