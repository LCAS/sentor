#!/usr/bin/env python3
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)
"""
#####################################################################################
from typing import Any, Callable, List, Dict, Optional
import rclpy
from rclpy.node import Node
import math
import numpy
from importlib import import_module
# imported math and numpy so they can be used in lambda expressions

def _import(location: str, name: str) -> Any:
    """Import a function from a module dynamically"""
    mod = import_module(location)
    return getattr(mod, name)

class ROSTopicFilter:
    """Filter for ROS topics that evaluates lambda functions on messages"""

    def __init__(self, topic_name: str, lambda_fn_str: str, config: Dict, throttle_val: int):
        """
        Initialize the topic filter
        
        Args:
            topic_name: Name of the topic to monitor
            lambda_fn_str: Lambda function as string or function name to import
            config: Configuration dictionary containing optional file and package names
            throttle_val: Process only every Nth message
        """
        self.topic_name = topic_name
        self.lambda_fn_str = lambda_fn_str
        self.config = config
        self.throttle_val = throttle_val
        self.throttle = self.throttle_val
        
        self.lambda_fn = None
        try:
            if config["file"] is not None and config["package"] is not None:
                self.lambda_fn = _import(f"{config['package']}.{config['file']}", self.lambda_fn_str)
            else:
                self.lambda_fn = eval(self.lambda_fn_str)
        except Exception as e:
            rclpy.logging.get_logger('ROSTopicFilter').error(
                f"Error evaluating lambda function {self.lambda_fn_str} : {e}")

        self.filter_satisfied = False
        self.unread_satisfied = False
        self.value_read = False
        self.sat_callbacks: List[Callable] = []
        self.unsat_callbacks: List[Callable] = []

    def callback_filter(self, msg: Any) -> None:
        """
        Filter callback that evaluates the lambda function on received messages
        
        Args:
            msg: The received message
        """
        if self.lambda_fn is None:
            return

        try:
            self.filter_satisfied = self.lambda_fn(msg)
        except Exception as e:
            rclpy.logging.get_logger('ROSTopicFilter').warn(
                f"Exception while evaluating {self.lambda_fn_str}: {e}")

        # if the last value was read: set value_read to False
        if self.value_read:
            self.value_read = False
        elif self.filter_satisfied:
            self.unread_satisfied = True

        if self.filter_satisfied:
            for func in self.sat_callbacks:
                func(self.lambda_fn_str, msg, self.config)
        else:
            for func in self.unsat_callbacks:
                func(self.lambda_fn_str)

    def callback_filter_throttled(self, msg: Any) -> None:
        """
        Throttled version of filter callback that processes every Nth message
        
        Args:
            msg: The received message
        """
        if (self.throttle % self.throttle_val) == 0:
            self.callback_filter(msg)
            self.throttle = 1
        else:
            self.throttle += 1

    def is_filter_satisfied(self) -> bool:
        """
        Check if the filter condition is satisfied
        
        Returns:
            True if the condition is satisfied, False otherwise
        """
        self.value_read = True

        if self.unread_satisfied:
            self.unread_satisfied = False
            return True

        return self.filter_satisfied

    def register_satisfied_cb(self, func: Callable) -> None:
        """
        Register a callback for when the filter condition becomes satisfied
        
        Args:
            func: Callback function to register
        """
        self.sat_callbacks.append(func)

    def register_unsatisfied_cb(self, func: Callable) -> None:
        """
        Register a callback for when the filter condition becomes unsatisfied
        
        Args:
            func: Callback function to register
        """
        self.unsat_callbacks.append(func)
#####################################################################################