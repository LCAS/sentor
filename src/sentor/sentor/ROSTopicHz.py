#!/usr/bin/env python3
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)

Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang

"""
#####################################################################################
import rclpy
from rclpy.qos import QoSProfile
from threading import Lock
import math
from threading import Event

class ROSTopicHz:
    def __init__(self, node, topic_name, window_size=1000, throttle_val=1, stop_event=None):
        self.node = node
        self.topic_name = topic_name
        self.window_size = window_size
        self.throttle_val = throttle_val if throttle_val > 0 else 1  # Avoid division by zero
        self.throttle = 0

        self.lock = Lock()
        self.last_printed_time = None
        self.prev_time = None
        self.times = []
        self.msg_tn = None
        self.node.get_logger().info(f"[ROSTopicHz] Initialized for {self.topic_name} with window {self.window_size}")
        # self._stop_event = Event()
        # Accept stop_event from outside or create internally
        self._stop_event = stop_event if stop_event is not None else Event()
        self.subscription = None
        self.enabled = True
        self.last_msg_time = None

    def start_monitoring(self, msg_type, qos_profile):
        if not self.subscription:
            self.subscription = self.node.create_subscription(
                msg_type, self.topic_name, self.callback_hz, qos_profile
            )
            # self.node.get_logger().info(f"[HzMonitor] Subscription to {self.topic_name} created")
            self.times.clear()
            self.last_msg_time = None
            self.enabled = True
            self.node.get_logger().info(f"[ROSTopicHz] Monitoring started for {self.topic_name}")

    def stop_monitoring(self):
        if self.subscription:
            self.node.destroy_subscription(self.subscription)
            self.subscription = None
            self.enabled = False
            self.node.get_logger().info(f"[ROSTopicHz] Monitoring stopped for {self.topic_name}")

    # def callback_hz(self, msg):
    #     if not self.enabled:
    #         return
    #     now = self.node.get_clock().now().nanoseconds / 1e9
    #     if self.last_msg_time is not None:
    #         delta = now - self.last_msg_time
    #         self.times.append(delta)
    #         if len(self.times) > self.window_size:
    #             self.times.pop(0)
    #     self.last_msg_time = now

    def callback_hz(self, msg):
        # if self._stop_event and self._stop_event.is_set():
        #     return
        # self.node.get_logger().info(f"[HzMonitor] callback_hz fired on {self.topic_name}")
        now = self.node.get_clock().now().nanoseconds / 1e9
        with self.lock:
            if self.last_msg_time is not None:
                dt = now - self.last_msg_time
                self.times.append(dt)
                if len(self.times) > self.window_size:
                    self.times.pop(0)
            self.last_msg_time = now

    def get_hz(self):
        if not self.enabled or len(self.times) == 0:
            return None
        if len(self.times) < 2:
            return None
        import statistics
        mean = sum(self.times) / len(self.times)
        stddev = statistics.stdev(self.times) if len(self.times) > 1 else 0.0
        return 1.0 / mean, min(self.times), max(self.times), stddev, len(self.times)

    # def callback_hz(self, msg):
    #     # self.node.get_logger().info(
    #     #     f"[HzMonitor] callback_hz triggered! times before: {len(self.times)}"
    #     # )
    #     if self._stop_event.is_set():
    #         return
        
    #     now = self.node.get_clock().now().nanoseconds / 1e9  # Time in seconds

    #     with self.lock:
    #         if self.prev_time is None:
    #             self.prev_time = now
    #             return

    #         delta = now - self.prev_time
    #         self.prev_time = now

    #         self.times.append(delta)
    #         if len(self.times) > self.window_size:
    #             self.times.pop(0)
    #     # self.node.get_logger().info(
    #     #     f"[HzMonitor] callback_hz done. times after: {len(self.times)}"
    #     # )
    # def callback_hz(self, msg):
    #     if self._stop_event and self._stop_event.is_set():
    #         return
    #     if not self.subscription:  # If the subscription was destroyed, do nothing
    #         return
    #     now = self.node.get_clock().now().nanoseconds / 1e9
    #     if self.last_msg_time is not None:
    #         delta = now - self.last_msg_time
    #         self.times.append(delta)
    #         if len(self.times) > self.window_size:
    #             self.times.pop(0)
    #     self.last_msg_time = now

    def callback_hz_throttled(self, msg):
        self.throttle += 1
        if self.throttle % self.throttle_val == 0:
            self.callback_hz(msg)

    # def get_hz(self):
    #     with self.lock:
    #         if not self.times or len(self.times) < 2:
    #             return None
            
    #         n = len(self.times)
    #         mean = sum(self.times) / n
    #         rate = 1.0 / mean if mean > 0 else 0.0
    #         std_dev = math.sqrt(sum((x - mean) ** 2 for x in self.times) / n)
    #         max_delta = max(self.times)
    #         min_delta = min(self.times)

    #         return rate, min_delta, max_delta, std_dev, n

    def print_hz(self, logger):
        stats = self.get_hz()
        if not stats:
            logger.info(f"[HzMonitor] No Hz stats yet. Waiting for more data.")
            return

        rate, min_d, max_d, std_d, n = stats
        logger.info(
            f"[HzMonitor] Rate={rate:.2f} Hz | Min={min_d:.3f}s | Max={max_d:.3f}s | Std={std_d:.4f}s | N={n}"
        )



