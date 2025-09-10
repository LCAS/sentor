#!/usr/bin/env python3
"""
Created on Thu Nov 21 10:30:22 2019
@author: Adam Binch (abinch@sagarobotics.com)

Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang

Description:
Topic name is needed. (Message type and QoS can be detected automatically) 
"""
#####################################################################################
#!/usr/bin/env python3
import rclpy
import importlib
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

class ROSTopicFilter:
    def __init__(self, parent_node: Node, topic_name, lambda_fn_str, config, throttle_val, stop_event=None):
        self.node = parent_node
        self.topic_name = topic_name
        self.lambda_fn_str = lambda_fn_str
        self.config = config
        self.throttle_val = max(throttle_val, 1)
        self.throttle_counter = 0
        self._stop_event = stop_event  # <- SAFE default

        self.sat_callbacks = []
        self.unsat_callbacks = []

        # Compile lambda function
        if isinstance(self.lambda_fn_str, str):
            try:
                self.lambda_fn = eval(self.lambda_fn_str)
            except Exception as e:
                self.node.get_logger().error(f"[ROSTopicFilter] Lambda error: {e}")
                self.lambda_fn = None
        else:
            # If it's already a callable (e.g. imported custom lambda), just assign it.
            self.lambda_fn = self.lambda_fn_str

        # Detect message type
        self.msg_type = self.get_message_type(self.topic_name)
        if not self.msg_type:
            self.node.get_logger().warn(f"[ROSTopicFilter] Could not detect message type for {self.topic_name}")
            return

        # Detect QoS
        qos = self.get_publisher_qos(self.topic_name)
        self.node.get_logger().info(f"[ROSTopicFilter] Using QoS: {qos}")

        # Create subscription
        self.subscription = self.node.create_subscription(
            self.msg_type,
            self.topic_name,
            self.callback_filter_throttled,
            qos
        )
        self.node.get_logger().info(f"[ROSTopicFilter] Subscribed to {self.topic_name}")

    def get_message_type(self, topic_name):
        topic_types = self.node.get_topic_names_and_types()
        for topic, types in topic_types:
            if topic == topic_name:
                msg_type_str = types[0]
                self.node.get_logger().info(f"[ROSTopicFilter] Detected msg type: {msg_type_str}")
                try:
                    pkg, msg = msg_type_str.split('/msg/')
                    module = importlib.import_module(f"{pkg}.msg")
                    return getattr(module, msg)
                except Exception as e:
                    self.node.get_logger().error(f"[ROSTopicFilter] Failed to import: {e}")
        return None

    def get_publisher_qos(self, topic_name):
        infos = self.node.get_publishers_info_by_topic(topic_name)
        if not infos:
            self.node.get_logger().warn(f"[ROSTopicFilter] No QoS info found for {topic_name}, using default.")
            return QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10,
                durability=DurabilityPolicy.VOLATILE
            )
        info = infos[0]
        return QoSProfile(
            reliability=info.qos_profile.reliability,
            durability=info.qos_profile.durability,
            history=info.qos_profile.history,
            depth=info.qos_profile.depth
        )

    def callback_filter(self, msg):
        if self._stop_event and self._stop_event.is_set():
            return

        if self.lambda_fn is None:
            return
        try:
            result = self.lambda_fn(msg)
            self.node.get_logger().info(f"[ROSTopicFilter] Lambda result: {result}")
            if result:
                for cb in self.sat_callbacks:
                    cb(self.lambda_fn_str, msg, self.config)
            else:
                for cb in self.unsat_callbacks:
                    cb(self.lambda_fn_str)
        except Exception as e:
            self.node.get_logger().error(f"[ROSTopicFilter] Lambda evaluation error: {e}")

    def callback_filter_throttled(self, msg):
        if self._stop_event and self._stop_event.is_set():
            return
        if self.throttle_counter % self.throttle_val == 0:
            self.callback_filter(msg)
            self.throttle_counter = 1
        else:
            self.throttle_counter += 1

    def register_satisfied_cb(self, func):
        self.sat_callbacks.append(func)

    def register_unsatisfied_cb(self, func):
        self.unsat_callbacks.append(func)

#####################################################################################