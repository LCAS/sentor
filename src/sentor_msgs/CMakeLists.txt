cmake_minimum_required(VERSION 3.5)
project(sentor_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/TopicMap.msg"
  "msg/TopicMapArray.msg"
  "msg/SentorEvent.msg"
  "msg/Monitor.msg"
  "msg/MonitorArray.msg"
  "srv/GetTopicMaps.srv"
  DEPENDENCIES std_msgs std_srvs
 )

ament_export_dependencies(rosidl_default_runtime std_msgs std_srvs)
ament_package()
