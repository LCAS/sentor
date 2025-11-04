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
import time
import statistics

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
        """
        Calculate the estimated frequency (Hz) of incoming messages based on recorded time intervals.

        This method uses a list of recorded time intervals (`self.times`) between consecutive messages
        to compute the mean, standard deviation, and estimated frequency (in Hz).
        If no messages have been received recently (i.e., the last interval exceeds twice the mean interval),
        the frequency is considered effectively zero.

        Returns:
            tuple or None:
                Returns a tuple containing:
                    - hz (float): Estimated frequency in Hz.
                    - min_time (float): Minimum recorded interval.
                    - max_time (float): Maximum recorded interval.
                    - stddev (float): Standard deviation of recorded intervals.
                    - count (int): Number of recorded intervals.
                Returns None if the monitor is disabled or no intervals are recorded.
        """

        # If monitoring is disabled or no time intervals are available, return None
        if not self.enabled or len(self.times) == 0:
            return None

        # Get the current system time
        now = time.time()

        # Calculate time since the last received message
        # If 'last_msg_time' attribute doesn't exist, assume infinite interval
        last_interval = now - self.last_msg_time if hasattr(self, 'last_msg_time') else float('inf')

        # Compute average (mean) interval between messages
        mean = sum(self.times) / len(self.times)

        # Compute standard deviation of the message intervals
        stddev = statistics.stdev(self.times) if len(self.times) > 1 else 0.0

        # Convert mean interval to frequency (Hz = 1 / mean interval)
        hz = 1.0 / mean

        # If no message has arrived for twice the average interval, consider rate effectively zero
        if last_interval > 2 * mean:  # threshold = 2 × mean interval
            hz = 0.0

        # Return the frequency and basic statistics
        return hz, min(self.times), max(self.times), stddev, len(self.times)


    # def get_hz(self):
    #     if not self.enabled or len(self.times) == 0:
    #         return None
    #     if len(self.times) < 2:
    #         return None
    #     import statistics
    #     mean = sum(self.times) / len(self.times)
    #     stddev = statistics.stdev(self.times) if len(self.times) > 1 else 0.0
    #     return 1.0 / mean, min(self.times), max(self.times), stddev, len(self.times)

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



