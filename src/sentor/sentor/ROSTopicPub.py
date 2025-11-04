#!/usr/bin/env python
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)

Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang
"""
#####################################################################################
# sentor/ROSTopicPub.py

import importlib
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import rclpy


class ROSTopicPub:
    def __init__(self, node, topic_name, msg_type=None, qos_profile=None, throttle_val=1):
        self.node = node
        self.topic_name = topic_name
        self.pub_callbacks = []
        self.throttle_val = throttle_val if throttle_val > 0 else 1
        self.throttle = self.throttle_val

        # Auto detect message type if not provided
        if msg_type is None:
            msg_type = self._detect_msg_type()
        self.msg_type = msg_type

        # Auto detect QoS if not provided
        if qos_profile is None:
            qos_profile = self._detect_qos_profile()
        self.qos_profile = qos_profile

        # Create subscription
        self.subscription = self.node.create_subscription(
            self.msg_type,
            self.topic_name,
            self.callback_pub_throttled,
            self.qos_profile
        )

        self.node.get_logger().info(f"[ROSTopicPub] Subscribed to {self.topic_name}")

    def _detect_msg_type(self):
        topic_types = self.node.get_topic_names_and_types()
        for topic, types in topic_types:
            if topic == self.topic_name and types:
                type_str = types[0]
                self.node.get_logger().info(f"[ROSTopicPub] Detected msg type: {type_str}")
                package, msg = type_str.split('/msg/')
                module = importlib.import_module(f"{package}.msg")
                return getattr(module, msg)
        self.node.get_logger().warn(f"[ROSTopicPub] Could not detect message type for {self.topic_name}, using fallback.")
        return None

    def _detect_qos_profile(self):
        infos = self.node.get_publishers_info_by_topic(self.topic_name)
        if infos:
            info = infos[0]
            qos = QoSProfile(
                reliability=info.qos_profile.reliability,
                durability=info.qos_profile.durability,
                history=info.qos_profile.history,
                depth=info.qos_profile.depth
            )
            self.node.get_logger().info(f"[ROSTopicPub] Using auto-detected QoS: {qos}")
            return qos
        else:
            self.node.get_logger().warn(f"[ROSTopicPub] No QoS info found, using fallback default.")
            return QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10
            )

    def callback_pub(self, msg):
        self.node.get_logger().debug(f"[ROSTopicPub] Received message on {self.topic_name}")
        for func in self.pub_callbacks:
            func(msg)

    def callback_pub_throttled(self, msg):
        if self.throttle % self.throttle_val == 0:
            self.callback_pub(msg)
            self.throttle = 1
        else:
            self.throttle += 1

    def register_published_cb(self, func):
        self.pub_callbacks.append(func)

