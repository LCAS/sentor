#!/usr/bin/env python3
"""
Created on Fri Dec  6 08:51:15 2019
@author: Adam Binch (abinch@sagarobotics.com)

Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang
"""
#####################################################################################
from threading import Event
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy, HistoryPolicy
from sentor_msgs.msg import Monitor, MonitorArray  # Ensure this message is defined

class MultiMonitor(Node):
    def __init__(self, node_name='multi_monitor'):
        super().__init__(node_name)

        # Declare and get safety publication rate from parameters
        self.declare_parameter("safety_pub_rate", 10.0)
        rate = self.get_parameter("safety_pub_rate").value

        self.topic_monitors = []
        self._stop_event = Event()
        self.error_code = []

        self.monitors_pub = None  # Initialized dynamically when first monitor is registered
        self.timer = self.create_timer(1.0 / rate, self.callback)

    def get_default_qos(self):
        """Fallback QoS profile if not provided by monitor."""
        qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL
        )
        self.get_logger().warn("[MultiMonitor] No QoS provided; using fallback default QoS.")
        return qos

    def register_monitor(self, topic_monitor):
        """Register a monitor and set QoS for MonitorArray publisher."""
        self.get_logger().info(f"[MultiMonitor] Registering monitor for topic: {topic_monitor.topic_name}")

        if not self.topic_monitors:
            qos_profile = topic_monitor.qos_profile or self.get_default_qos()
            self.monitors_pub = self.create_publisher(MonitorArray, "/sentor/monitors", qos_profile)

        self.topic_monitors.append(topic_monitor)

    def callback(self):
        """Periodic check and publish monitor states."""
        if not self._stop_event.is_set() and self.monitors_pub is not None:
            error_code_new = [
                monitor.conditions[expr]["satisfied"]
                for monitor in self.topic_monitors
                for expr in monitor.conditions
            ]

            if error_code_new != self.error_code:
                self.error_code = error_code_new

                msg = MonitorArray()
                msg.header.stamp = self.get_clock().now().to_msg()
                count = 0

                for monitor in self.topic_monitors:
                    for expr in monitor.conditions:
                        condition = Monitor()
                        condition.topic = monitor.topic_name
                        condition.condition = expr  # Now 'expr' is the original string, e.g., "CustomLambda"
                        condition.safety_critical = monitor.conditions[expr]["safety_critical"]
                        condition.autonomy_critical = monitor.conditions[expr]["autonomy_critical"]
                        condition.satisfied = self.error_code[count]
                        condition.tags = monitor.conditions[expr].get("tags", [])
                        msg.conditions.append(condition)
                        count += 1

                self.monitors_pub.publish(msg)

    def stop_monitor(self):
        self._stop_event.set()

    def start_monitor(self):
        self._stop_event.clear()


# import rclpy
# from rclpy.node import Node
# from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy, HistoryPolicy
# from threading import Event
# from sentor_msgs.msg import Monitor, MonitorArray  # Import ROS2 messages


# class MultiMonitor(Node):
#     def __init__(self, node_name='multi_monitor'):
#         """ Initialize MultiMonitor Node. """
#         super().__init__(node_name)

#         # Declare and get the safety publication rate parameter
#         self.declare_parameter("safety_pub_rate", 10.0)
#         rate = self.get_parameter("safety_pub_rate").value

#         self.topic_monitors = []
#         self._stop_event = Event()
#         self.error_code = []

#         self.monitors_pub = None  # Will be set dynamically

#         # Create a timer for periodic execution of the callback
#         period = 1.0 / rate
#         self.timer = self.create_timer(period, self.callback)

#     def get_default_qos(self):
#         """ Provide a fallback default QoS profile. """
#         qos = QoSProfile(
#             depth=1,
#             reliability=QoSReliabilityPolicy.RELIABLE,
#             history=HistoryPolicy.KEEP_LAST,
#             durability=QoSDurabilityPolicy.TRANSIENT_LOCAL
#         )
#         self.get_logger().warn("[MultiMonitor] No QoS provided; using fallback default QoS.")
#         return qos

#     def register_monitors(self, topic_monitor):
#         """ Register a new monitor and set up QoS dynamically. """
#         self.get_logger().info(f"[MultiMonitor] Registering monitor for topic: {topic_monitor.topic_name}")

#         # If this is the first topic, set the publisher QoS based on it (or fallback default)
#         if not self.topic_monitors:
#             qos_profile = topic_monitor.qos_profile or self.get_default_qos()
#             self.monitors_pub = self.create_publisher(
#                 MonitorArray, "/sentor/monitors", qos_profile
#             )

#         self.topic_monitors.append(topic_monitor)

#     def callback(self):
#         """ Periodically check conditions and publish monitor status. """
#         if not self._stop_event.is_set() and self.monitors_pub is not None:
#             error_code_new = [
#                 monitor.conditions[expr]["satisfied"]
#                 for monitor in self.topic_monitors
#                 for expr in monitor.conditions
#             ]

#             # Publish only if there is a change in error_code
#             if error_code_new != self.error_code:
#                 self.error_code = error_code_new

#                 conditions = MonitorArray()
#                 conditions.header.stamp = self.get_clock().now().to_msg()

#                 count = 0
#                 for monitor in self.topic_monitors:
#                     topic_name = monitor.topic_name
#                     for expr in monitor.conditions:
#                         condition = Monitor()
#                         condition.topic = topic_name
#                         condition.condition = expr
#                         condition.safety_critical = monitor.conditions[expr]["safety_critical"]
#                         condition.autonomy_critical = monitor.conditions[expr]["autonomy_critical"]
#                         condition.satisfied = self.error_code[count]
#                         condition.tags = monitor.conditions[expr]["tags"]
#                         conditions.conditions.append(condition)
#                         count += 1

#                 self.monitors_pub.publish(conditions)

#     def stop_monitor(self):
#         """ Stop monitoring. """
#         self._stop_event.set()

#     def start_monitor(self):
#         """ Start monitoring. """
#         self._stop_event.clear()


 

# import rclpy
# from rclpy.node import Node
# from rclpy.qos import QoSProfile, QoSDurabilityPolicy
# from threading import Event

# # Assuming these message definitions are available in your ROS2 package.
# from sentor.msg import Monitor, MonitorArray


# class MultiMonitor(Node):
#     # def __init__(self, node_name='multi_monitor'):
#     #     super().__init__(node_name)
        
#     #     # Declare and get the safety_pub_rate parameter
#     #     self.declare_parameter("safety_pub_rate", 10.0)
#     #     rate = self.get_parameter("safety_pub_rate").value
        
#     #     self.topic_monitors = []
#     #     self._stop_event = Event()
#     #     self.error_code = []

#     #     # Create publisher with transient local durability to mimic latching in ROS1
#     #     qos_profile = QoSProfile(depth=1)
#     #     qos_profile.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
#     #     self.monitors_pub = self.create_publisher(MonitorArray, "/sentor/monitors", qos_profile)

#     #     # Create a timer; in ROS2, the timer callback does not receive an event argument.
#     #     period = 1.0 / rate
#     #     self.timer = self.create_timer(period, self.callback)
    
#     # def register_monitors(self, topic_monitor):
#     #     """
#     #     Register a new monitor to be included in the callback processing.
#     #     """
#     #     self.topic_monitors.append(topic_monitor)
        
#     # def callback(self):
#     #     if not self._stop_event.is_set():
#     #         # Gather the 'satisfied' status from all monitors
#     #         error_code_new = [
#     #             monitor.conditions[expr]["satisfied"]
#     #             for monitor in self.topic_monitors
#     #             for expr in monitor.conditions
#     #         ]
            
#     #         # Publish only if there is a change in error_code
#     #         if error_code_new != self.error_code:
#     #             self.error_code = error_code_new
                
#     #             conditions = MonitorArray()
#     #             # Set the header stamp using ROS2 time
#     #             conditions.header.stamp = self.get_clock().now().to_msg()
                
#     #             count = 0
#     #             for monitor in self.topic_monitors:
#     #                 topic_name = monitor.topic_name
#     #                 for expr in monitor.conditions:
#     #                     condition = Monitor()
#     #                     condition.topic = topic_name
#     #                     condition.condition = expr
#     #                     condition.safety_critical = monitor.conditions[expr]["safety_critical"]
#     #                     condition.autonomy_critical = monitor.conditions[expr]["autonomy_critical"]
#     #                     condition.satisfied = self.error_code[count]
#     #                     condition.tags = monitor.conditions[expr]["tags"]
#     #                     conditions.conditions.append(condition)
#     #                     count += 1

#     #             self.monitors_pub.publish(conditions)
#     def __init__(self, node_name='multi_monitor'):
#         super().__init__(node_name)
        
#         # Declare and get the safety_pub_rate parameter
#         self.declare_parameter("safety_pub_rate", 10.0)
#         rate = self.get_parameter("safety_pub_rate").value

#         self.topic_monitors = []
#         self._stop_event = Event()
#         self.error_code = []

#         # Create publisher with transient local durability to mimic latching in ROS1
#         qos_profile = QoSProfile(depth=1)
#         qos_profile.durability = QoSDurabilityPolicy.TRANSIENT_LOCAL
#         self.monitors_pub = self.create_publisher(MonitorArray, "/sentor/monitors", qos_profile)

#         # Create a timer
#         period = 1.0 / rate
#         self.timer = self.create_timer(period, self.callback)

#         self.get_logger().info("MultiMonitor node started!")  # 🔹 Log startup
        
#     def register_monitors(self, topic_monitor):
#         """ Register a new monitor to be included in the callback processing. """
#         self.get_logger().info(f"Registering monitor for topic: {topic_monitor.topic_name}")
#         self.topic_monitors.append(topic_monitor)
#         self.get_logger().info(f"Total monitors registered: {len(self.topic_monitors)}")  # 🔹 Log monitor count

#     def callback(self):
#         self.get_logger().info(f"MultiMonitor callback running... Monitors count: {len(self.topic_monitors)}")

#         if not self._stop_event.is_set():
#             error_code_new = [
#                 monitor.conditions[expr]["satisfied"]
#                 for monitor in self.topic_monitors
#                 for expr in monitor.conditions
#             ]

#             self.get_logger().info(f"Previous error_code: {self.error_code}")
#             self.get_logger().info(f"New error_code: {error_code_new}")

#             if error_code_new != self.error_code:
#                 self.get_logger().info("Publishing a new MonitorArray message.")
#                 self.error_code = error_code_new

#                 conditions = MonitorArray()
#                 conditions.header.stamp = self.get_clock().now().to_msg()
                
#                 count = 0
#                 for monitor in self.topic_monitors:
#                     topic_name = monitor.topic_name
#                     for expr in monitor.conditions:
#                         condition = Monitor()
#                         condition.topic = topic_name
#                         condition.condition = expr
#                         condition.safety_critical = monitor.conditions[expr]["safety_critical"]
#                         condition.autonomy_critical = monitor.conditions[expr]["autonomy_critical"]
#                         condition.satisfied = self.error_code[count]
#                         condition.tags = monitor.conditions[expr]["tags"]
#                         conditions.conditions.append(condition)
#                         count += 1

#                 self.monitors_pub.publish(conditions)

#     def stop_monitor(self):
#         self._stop_event.set()

#     def start_monitor(self):
#         self._stop_event.clear()

# def main(args=None):
#     """ Entry point for the node """
#     rclpy.init(args=args)
#     node = MultiMonitor()

#     # Keep the node alive
#     rclpy.spin(node)

#     # Cleanup after shutdown
#     node.destroy_node()
#     rclpy.shutdown()


# if __name__ == "__main__":
#     main()