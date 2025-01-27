#!/usr/bin/env python3
"""
Created on Fri Dec  6 08:51:15 2019

@author: Adam Binch (abinch@sagarobotics.com)
Modified for ROS2
"""
#####################################################################################
from typing import List, Any
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.time import Time
from sentor.msg import Monitor, MonitorArray
from threading import Event


class MultiMonitor:
    def __init__(self):
        """Initialize multi-monitor for tracking multiple topic monitors"""
        # Create ROS2 node
        self.node = rclpy.create_node('multi_monitor')
        self.callback_group = ReentrantCallbackGroup()
        
        # Get parameters
        self.rate = self.node.declare_parameter('safety_pub_rate', 10.0).value
        
        self.topic_monitors: List[Any] = []
        self._stop_event = Event()
        self.error_code: List[bool] = []
        
        # Create publisher with QoS profile
        self.monitors_pub = self.node.create_publisher(
            MonitorArray,
            '/sentor/monitors',
            qos_profile=1  # Keep last, with durability TRANSIENT_LOCAL for latching behavior
        )
        
        # Create timer for monitor checking
        self.timer = self.node.create_timer(
            1.0/self.rate,
            self.callback,
            callback_group=self.callback_group
        )

    def register_monitors(self, topic_monitor: Any) -> None:
        """Register a topic monitor"""
        self.topic_monitors.append(topic_monitor)
        
    def callback(self) -> None:
        """Callback for checking monitor states and publishing updates"""
        if not self._stop_event.isSet():
            error_code_new = [
                monitor.conditions[expr]["satisfied"] 
                for monitor in self.topic_monitors 
                for expr in monitor.conditions
            ]
            
            if error_code_new != self.error_code:
                self.error_code = error_code_new
                
                conditions = MonitorArray()
                conditions.header.stamp = self.node.get_clock().now().to_msg()
                
                count = 0                
                for monitor in self.topic_monitors:
                    topic_name = monitor.topic_name
                    
                    for expr in monitor.conditions:
                        condition = Monitor()
                        condition.topic = topic_name
                        condition.condition = expr
                        condition.safety_critical = monitor.conditions[expr]["safety_critical"]
                        condition.autonomy_critical = monitor.conditions[expr]["autonomy_critical"]
                        condition.satisfied = self.error_code[count]
                        condition.tags = monitor.conditions[expr]["tags"]
                        conditions.conditions.append(condition)
                        count += 1
                        
                self.monitors_pub.publish(conditions)
                
    def stop_monitor(self) -> None:
        """Stop the multi-monitor"""
        self._stop_event.set()

    def start_monitor(self) -> None:
        """Start the multi-monitor"""
        self._stop_event.clear()

    def cleanup(self) -> None:
        """Cleanup ROS2 node"""
        self.node.destroy_node()
#####################################################################################