#!/usr/bin/env python3
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)

Modified from https://github.com/strawlab/ros_comm/blob/master/tools/rostopic/src/rostopic.py
Adapted for ROS2
"""
#####################################################################################
import rclpy
from rclpy.clock import Clock
import threading
import math
from typing import Optional, Callable


class ROSTopicHz:
    """
    ROSTopicHz receives messages for a topic and computes frequency stats
    """
    def __init__(self, topic_name: str, window_size: int, throttle_val: int, filter_expr: Optional[Callable] = None):
        """
        Initialize ROSTopicHz monitor
        
        Args:
            topic_name: Name of the topic to monitor
            window_size: Number of messages to keep in statistics window
            throttle_val: Only process every Nth message
            filter_expr: Optional filter function for messages
        """
        self.lock = threading.Lock()
        self.last_printed_tn = 0
        self.msg_t0 = -1.0
        self.msg_tn = 0
        self.times = []
        self.filter_expr = filter_expr
        self.topic_name = topic_name
        
        # Can't have infinite window size due to memory restrictions
        if window_size < 0:
            window_size = 50000
        self.window_size = window_size
        
        self.throttle_val = throttle_val
        self.throttle = self.throttle_val
        
        # Create clock for time keeping
        self.clock = Clock()

    def callback_hz(self, msg):
        """
        ROS subscription callback for frequency monitoring
        
        Args:
            msg: The received message
        """
        # Skip messages that don't match filter
        if self.filter_expr is not None and not self.filter_expr(msg):
            return
            
        with self.lock:
            curr_rostime = self.clock.now()

            # Handle time reset
            if curr_rostime.nanoseconds == 0:
                if len(self.times) > 0:
                    print("time has reset, resetting counters")
                    self.times = []
                return

            curr = curr_rostime.nanoseconds / 1e9  # Convert to seconds
            if self.msg_t0 < 0 or self.msg_t0 > curr:
                self.msg_t0 = curr
                self.msg_tn = curr
                self.times = []
            else:
                self.times.append(curr - self.msg_tn)
                self.msg_tn = curr

            # Only keep statistics for the last window_size messages
            if len(self.times) > self.window_size - 1:
                self.times.pop(0)

    def callback_hz_throttled(self, msg):
        """
        Throttled version of the callback that only processes every Nth message
        
        Args:
            msg: The received message
        """
        if (self.throttle % self.throttle_val) == 0:
            self.callback_hz(msg)
            self.throttle = 1
        else:
            self.throttle += 1

    def print_hz(self):
        """
        Print the average publishing rate to screen
        """
        if not self.times:
            return
        elif self.msg_tn == self.last_printed_tn:
            print("no new messages")
            return
            
        with self.lock:
            # Calculate frequency statistics
            n = len(self.times)
            mean = sum(self.times) / n
            rate = 1./mean if mean > 0. else 0

            # Calculate standard deviation
            std_dev = math.sqrt(sum((x - mean)**2 for x in self.times) / n)

            # Get min and max deltas
            max_delta = max(self.times)
            min_delta = min(self.times)

            self.last_printed_tn = self.msg_tn
            
        print(f"average rate: {rate:.3f}\n\tmin: {min_delta:.3f}s max: {max_delta:.3f}s std dev: {std_dev:.5f}s window: {n+1}")

    def get_hz(self) -> Optional[float]:
        """
        Get the average publishing rate
        
        Returns:
            The calculated publishing rate in Hz, or None if no new messages
        """
        if not self.times:
            return None
        elif self.msg_tn == self.last_printed_tn:
            return None
            
        with self.lock:
            n = len(self.times)
            mean = sum(self.times) / n
            rate = 1./mean if mean > 0. else 0
            self.last_printed_tn = self.msg_tn
            
        return rate
#####################################################################################