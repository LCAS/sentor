#!/usr/bin/env python3
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)
Adapted for ROS2
"""
#####################################################################################
from typing import Any, Callable, List
import rclpy
from rclpy.node import Node


class ROSTopicPub:
    """Monitor publication of ROS topics"""

    def __init__(self, topic_name: str, throttle_val: int):
        """
        Initialize the topic publication monitor
        
        Args:
            topic_name: Name of the topic to monitor
            throttle_val: Process only every Nth message
        """
        self.topic_name = topic_name
        self.pub_callbacks: List[Callable] = []
        self.throttle_val = throttle_val
        self.throttle = self.throttle_val

    def callback_pub(self, msg: Any) -> None:
        """
        Callback for when a message is published
        
        Args:
            msg: The received message
        """
        for func in self.pub_callbacks:
            func("'published'")
            
    def callback_pub_throttled(self, msg: Any) -> None:
        """
        Throttled version of publication callback that processes every Nth message
        
        Args:
            msg: The received message
        """
        if (self.throttle % self.throttle_val) == 0:
            self.callback_pub(msg)
            self.throttle = 1
        else:
            self.throttle += 1

    def register_published_cb(self, func: Callable) -> None:
        """
        Register a callback for when messages are published
        
        Args:
            func: Callback function to register
        """
        self.pub_callbacks.append(func)
#####################################################################################