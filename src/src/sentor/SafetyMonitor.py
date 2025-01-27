#!/usr/bin/env python3
"""
Created on Fri Dec  6 08:51:15 2019

@author: Adam Binch (abinch@sagarobotics.com)
Modified for ROS2
"""
#####################################################################################
from typing import List, Any, Optional
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.timer import Timer
from std_msgs.msg import Bool
from std_srvs.srv import SetBool
from threading import Event


class SafetyMonitor:
    def __init__(self, topic: str, event_msg: str, attr: str, srv: str, 
                 event_cb: callable, invert: bool = False):
        """
        Initialize safety monitor
        
        Args:
            topic: Topic to publish safety status
            event_msg: Message prefix for events
            attr: Attribute name to monitor in topic monitors
            srv: Service name for safety control
            event_cb: Callback for reporting events
            invert: Whether to invert the safety status
        """
        # Create ROS2 node
        self.node = rclpy.create_node('safety_monitor')
        self.callback_group = ReentrantCallbackGroup()
        
        # Get parameters
        self.timeout = self.node.declare_parameter('safe_operation_timeout', 10.0).value
        self.rate = self.node.declare_parameter('safety_pub_rate', 10.0).value
        self.auto_tagging = self.node.declare_parameter('auto_safety_tagging', True).value

        if self.timeout <= 0:
            self.timeout = 0.1
        
        self.attr = attr
        self.event_cb = event_cb
        self.invert = invert
        self.topic_monitors: List[Any] = []
        
        self.timer: Optional[Timer] = None
        self.safe_operation = False        
        self.safe_msg_sent = False
        self.unsafe_msg_sent = False
        
        self._stop_event = Event()

        self.event_msg = event_msg + ": "

        # Create publisher with QoS profile
        self.safety_pub = self.node.create_publisher(
            Bool,
            topic,
            10
        )
        
        # Create timer for safety publishing
        self.safety_timer = self.node.create_timer(
            1.0/self.rate,
            self.safety_pub_cb,
            callback_group=self.callback_group
        )
        
        # Create service
        self.srv = self.node.create_service(
            SetBool,
            f'/sentor/{srv}',
            self.srv_cb,
            callback_group=self.callback_group
        )

    def register_monitors(self, topic_monitor: Any) -> None:
        """Register a topic monitor"""
        self.topic_monitors.append(topic_monitor)
        
    def safety_pub_cb(self) -> None:
        """Callback for safety status publishing"""
        if not self._stop_event.isSet():
            if self.topic_monitors:
                threads_are_safe = [getattr(monitor, self.attr) for monitor in self.topic_monitors]
                
                if self.auto_tagging and all(threads_are_safe) and self.timer is None:
                    self.timer = self.node.create_timer(
                        self.timeout,
                        self.timer_cb,
                        callback_group=self.callback_group
                    )
                    
                if not all(threads_are_safe):
                    if self.timer is not None:
                        self.timer.cancel()
                        self.timer = None

                    self.safe_operation = False                        
                    if not self.unsafe_msg_sent:
                        self.event_cb(self.event_msg + "FALSE", "error")
                        self.safe_msg_sent = False
                        self.unsafe_msg_sent = True

                msg = Bool()
                msg.data = not self.safe_operation if self.invert else self.safe_operation
                self.safety_pub.publish(msg)

    def timer_cb(self) -> None:
        """Callback for safety timeout timer"""
        self.safe_operation = True
        if not self.safe_msg_sent:
            self.event_cb(self.event_msg + "TRUE", "info")
            self.safe_msg_sent = True
            self.unsafe_msg_sent = False
                                       
    def srv_cb(self, request: SetBool.Request, response: SetBool.Response) -> SetBool.Response:
        """Callback for safety control service"""
        self.safe_operation = request.data        
        
        response.success = True
        response.message = f"{self.event_msg}{request.data}"
        
        return response
        
    def stop_monitor(self) -> None:
        """Stop the safety monitor"""
        self._stop_event.set()

    def start_monitor(self) -> None:
        """Start the safety monitor"""
        self._stop_event.clear()

    def cleanup(self) -> None:
        """Cleanup ROS2 node"""
        self.node.destroy_node()
#####################################################################################