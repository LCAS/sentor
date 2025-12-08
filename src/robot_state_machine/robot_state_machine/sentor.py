#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Bool, String
from datetime import datetime
import time

class Sentor(Node):
    def __init__(self):
        super().__init__('sentor_node')
        now = time.time()

        # Track last-received times for heartbeats (only bridge now)
        self.critical_heartbeats = {
            'arduino_bridge_alive': {'last': now, 'timeout': 0.5},
        }
        self.noncritical_heartbeats = {
            'localization_lost': {'last': now, 'timeout': 1.0},
            'operator_touch':    {'last': now, 'timeout': 30.0},
            'obstacle_detected': {'last': now, 'timeout': 1.0},
        }

        # State for event logging and previous issues
        self._last_estop = False
        self._last_collision = False
        self._prev_missing_crit_hb = set()
        self._prev_missing_noncrit_hb = set()
        self._prev_issues = set()

        # QoS profiles
        qos_crit = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )
        qos_noncrit = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)

        # Publishers
        self.pub_crit_hb = self.create_publisher(Bool, '/sentor/heartbeat_critical', qos_crit)
        self.pub_noncrit_hb = self.create_publisher(Bool, '/sentor/heartbeat_noncritical', qos_crit)
        self.pub_log = self.create_publisher(String, '/sentor/log', qos_crit)

        # Subscriptions for heartbeat topics
        for t in self.critical_heartbeats:
            self.create_subscription(Bool, t, lambda msg, t=t: self._hb_mark(t), qos_noncrit)
        for t in self.noncritical_heartbeats:
            self.create_subscription(Bool, t, lambda msg, t=t: self._hb_mark(t), qos_noncrit)

        # Subscriptions for estop, collision
        self.create_subscription(Bool, '/estop_pressed',      self._cb_estop,      10)
        self.create_subscription(Bool, '/collision_detected', self._cb_collision,  10)

        # Periodic check timer
        self.create_timer(0.1, self._check)

    def _hb_mark(self, topic):
        # Reset heartbeat timer for given topic
        now = time.time()
        if topic in self.critical_heartbeats:
            self.critical_heartbeats[topic]['last'] = now
        else:
            self.noncritical_heartbeats[topic]['last'] = now

    def _cb_estop(self, msg: Bool):
        # Log on press and recovery
        if msg.data and not self._last_estop:
            self.log_with_time("Critical event: E-stop pressed", 'error')
        elif not msg.data and self._last_estop:
            self.log_with_time("Recovered: E-stop cleared", 'info')
        self._last_estop = msg.data

    def _cb_collision(self, msg: Bool):
        # Log on collision and recovery
        if msg.data and not self._last_collision:
            self.log_with_time("Critical event: Collision detected", 'error')
        elif not msg.data and self._last_collision:
            self.log_with_time("Recovered: collision cleared", 'info')
        self._last_collision = msg.data


    def _check(self):
        now = time.time()
        # Check heartbeat deadlines
        missing_crit_hb = { name for name, info in self.critical_heartbeats.items() if now - info['last'] > info['timeout'] }
        missing_noncrit_hb = { name for name, info in self.noncritical_heartbeats.items() if now - info['last'] > info['timeout'] }

        # Log recoveries/misses
        for name in self._prev_missing_crit_hb - missing_crit_hb:
            self.log_with_time(f"Recovered: critical heartbeat '{name}'", 'info')
        for name in missing_crit_hb - self._prev_missing_crit_hb:
            self.log_with_time(f"Critical missed heartbeat: '{name}'", 'error')

        for name in self._prev_missing_noncrit_hb - missing_noncrit_hb:
            self.log_with_time(f"Recovered: noncritical heartbeat '{name}'", 'info')
        for name in missing_noncrit_hb - self._prev_missing_noncrit_hb:
            self.log_with_time(f"Non-critical missed heartbeat: '{name}'", 'warn')

        # Publish periodic heartbeats
        if not missing_crit_hb:
            self.pub_crit_hb.publish(Bool(data=not missing_crit_hb))
        self.pub_noncrit_hb.publish(Bool(data=not missing_noncrit_hb))

        # Combined issues summary
        issues = set()
        for name in missing_crit_hb: issues.add(f"heartbeat missed:{name}")
        for name in missing_noncrit_hb: issues.add(f"heartbeat warn:{name}")
        if self._last_estop: issues.add("E-stop pressed")
        if self._last_collision: issues.add("Collision detected")

        if issues != self._prev_issues:
            if not issues:
                self.log_with_time("All systems operational", 'info')
            else:
                summary = "Current issues -> " + "; ".join(sorted(issues))
                self.log_with_time(summary, 'warn')
            self._prev_issues = issues

        self._prev_missing_crit_hb = missing_crit_hb
        self._prev_missing_noncrit_hb = missing_noncrit_hb

    def log_with_time(self, text, level='info'):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{now}] {text}"
        # Use fixed methods to avoid changing logger severity
        if level == 'info':
            self.get_logger().info(msg)
        elif level == 'warn':
            self.get_logger().warning(msg)
        elif level == 'error':
            self.get_logger().error(msg)
        self.pub_log.publish(String(data=msg))


def main(args=None):
    rclpy.init(args=args)
    node = Sentor()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()