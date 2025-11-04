# SafetyMonitor.py
#!/usr/bin/env python
"""
Created on Fri Dec  6 08:51:15 2019

@author: Adam Binch

Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang
"""
import threading
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from example_interfaces.srv import SetBool

class SafetyMonitor(Node):
    def __init__(
        self,
        topic: str,
        event_msg: str,
        attr: str,
        srv_name: str,
        event_cb,
        invert: bool = False,
    ):
        super().__init__('safety_monitor')

        # parameters
        self.declare_parameter('safe_operation_timeout', 10.0)
        self.declare_parameter('safety_pub_rate',        1.0)
        self.declare_parameter('auto_safety_tagging',    True)

        self.timeout      = self.get_parameter('safe_operation_timeout').value or 0.1
        self.rate         = self.get_parameter('safety_pub_rate').value
        self.auto_tagging = self.get_parameter('auto_safety_tagging').value

        # internal state
        self.attr             = attr
        self.event_cb         = event_cb
        self.invert           = invert
        self.topic_monitors   = []
        self.timer            = None
        self.safe_operation   = False
        self.safe_msg_sent    = False
        self.unsafe_msg_sent  = False
        self._stop_event      = threading.Event()
        self.event_msg        = f"{event_msg}: "

        # publisher + periodic callback
        self.safety_pub = self.create_publisher(Bool, topic, 10)
        self.create_timer(1.0 / self.rate, self._safety_pub_cb)

        # override service
        self.create_service(SetBool, f'/sentor/{srv_name}', self._srv_cb)

    def register_monitor(self, m):
        """m can be a TopicMonitor (has .topic_name) or NodeMonitor (has .target)."""
        self.topic_monitors.append(m)
        # cancel any pending countdown
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def _safety_pub_cb(self):
        if self._stop_event.is_set() or not self.topic_monitors:
            return

        states = []
        for m in self.topic_monitors:
            # first, let each monitor refresh its .is_alive/.is_autonomy_alive
            if hasattr(m, '_check_alive_status'):
                m._check_alive_status()

            alive = getattr(m, self.attr)
            # pick human‐readable name: topic_name or target
            name = getattr(m, 'topic_name', None) or getattr(m, 'target', '<unknown>')
            self.get_logger().info(f"[SAFETY] {name}.{self.attr} = {alive}")
            states.append(alive)

        # arm the “all good” timer if needed
        if self.auto_tagging and all(states) and self.timer is None:
            self.timer = self.create_timer(self.timeout, self._timer_cb)

        # cancel countdown and mark unsafe if any dead
        if not all(states):
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.safe_operation = False
            if not self.unsafe_msg_sent:
                self.event_cb(self.event_msg + "FALSE", "error")
                self.unsafe_msg_sent = True
                self.safe_msg_sent = False

        # publish the Bool
        msg = Bool()
        msg.data = (not self.safe_operation) if self.invert else self.safe_operation
        self.safety_pub.publish(msg)

    def _timer_cb(self):
        # countdown complete → mark safe
        self.safe_operation = True
        if not self.safe_msg_sent:
            self.event_cb(self.event_msg + "TRUE", "info")
            self.safe_msg_sent   = True
            self.unsafe_msg_sent = False

        # one-shot timer
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def _srv_cb(self, request, response):
        # manual override / reset
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.safe_operation = request.data
        response.success = True
        response.message = f"{self.event_msg}{request.data}"
        return response

    def stop_monitor(self):
        self._stop_event.set()

    def start_monitor(self):
        self._stop_event.clear()
