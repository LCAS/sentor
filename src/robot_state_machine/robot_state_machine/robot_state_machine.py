#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import time

class RobotStateMachine(Node):
    def __init__(self):
        super().__init__('robot_state_machine')

        self.states = ['start-up', 'disabled', 'enabled', 'active']
        self.current_state = 'start-up'


        self._warned_noncrit = False

        self.noncrit_ok = True
        self._recover_from_noncrit = False
        self._last_localization_lost = False

        self.state_pub = self.create_publisher(String, 'robot_state', 10)
        self.autonomous_pub = self.create_publisher(Bool, 'autonomous_mode', 10)

        self.declare_parameter('autonomous_mode', False)
        self.autonomous_mode = self.get_parameter('autonomous_mode').value
        self.autonomous_pub.publish(Bool(data=self.autonomous_mode))

        self.publish_state()


        self.last_deadman = time.time()
        self.deadman_timeout = 0.5
        self.create_timer(0.1, self._deadman_watchdog)

        self._last_crit_hb = time.time()
        self._last_noncrit_hb = time.time()
        self._crit_hb_to = 0.5
        self._noncrit_hb_to = 0.5
        self.create_subscription(Bool, '/sentor/heartbeat_critical', self._crit_hb_cb, 10)
        self.create_subscription(Bool, '/sentor/heartbeat_noncritical', self._noncrit_hb_cb, 10)
        self.create_timer(0.1, self._check_heartbeats)

        self.startup_timer = self.create_timer(3.0, self.startup_complete)
        self.autonomous_active_timer = None

        self.create_subscription(String, 'set_mode', self.set_mode_selector_callback, 10)
        self.create_subscription(String, 'set_state', self.set_state_selector_callback, 10)
        self.create_subscription(Bool, 'deadman_button', self.deadman_callback, 10)


    def publish_state(self):
        msg = String(data=self.current_state)
        self.state_pub.publish(msg)
        self.get_logger().info(f'Robot state: {self.current_state}')

    def set_state(self, new_state):
        if new_state != self.current_state:
            self.current_state = new_state
            if new_state == 'enabled':
                self._warned_noncrit = False
            self.publish_state()

    def startup_complete(self):
        self.startup_timer.cancel()
        self.set_state('disabled')

    def set_mode_selector_callback(self, msg):
        req = msg.data.lower()
        if req not in ['manual', 'autonomous']:
            self.get_logger().warn(f"Ignoring invalid mode: {req}")
            return
        new_mode = (req == 'autonomous')
        if new_mode != self.autonomous_mode:
            self.autonomous_mode = new_mode
            self.get_logger().info(f"Mode switched to {req}")
            self.autonomous_pub.publish(Bool(data=self.autonomous_mode))

            if self.current_state == 'active':
                self.get_logger().info(f"Mode change while ACTIVE → ENABLED")
                self.set_state('enabled')
                self._recover_from_noncrit = False
                self.handle_enabled_entry()

    def set_state_selector_callback(self, msg):
        req = msg.data.lower()
        valid = {'disabled': ['enabled'], 'enabled': ['disabled', 'active'], 'active': ['enabled', 'disabled']}
        if req not in self.states:
            self.get_logger().warn(f"Ignoring invalid state: {req}")
            return
        if req == self.current_state:
            self.get_logger().info(f"Already in {req}")
            return
        if req in valid.get(self.current_state, []):
            self.get_logger().info(f"Transition {self.current_state} → {req}")
            self.set_state(req)
            if req == 'enabled':
                self._recover_from_noncrit = False
                self.handle_enabled_entry()
        else:
            self.get_logger().warn(f"Illegal transition {self.current_state} → {req}")

    def handle_enabled_entry(self):
        if self.autonomous_active_timer:
            self.autonomous_active_timer.cancel()

        if self.autonomous_mode and self.noncrit_ok and self._recover_from_noncrit:
            self.autonomous_active_timer = self.create_timer(3.0, self.autonomous_go_active)

    def autonomous_go_active(self):
        if (self.current_state == 'enabled'
            and self.autonomous_mode
            and self.noncrit_ok):
            self.autonomous_active_timer.cancel()
            self.autonomous_active_timer = None
            self.set_state('active')
            self._recover_from_noncrit = False

    def deadman_callback(self, msg):
        self.last_deadman = time.time()
        if not self.autonomous_mode:
            if self.current_state == 'enabled' and msg.data:
                self.get_logger().info('Deadman pressed → ACTIVE')
                self.set_state('active')
            elif self.current_state == 'active' and not msg.data:
                self.get_logger().info('Deadman released → ENABLED')
                self.set_state('enabled')
                self._recover_from_noncrit = False

    def _deadman_watchdog(self):
        if not self.autonomous_mode and self.current_state == 'active':
            if time.time() - self.last_deadman > self.deadman_timeout:
                self.get_logger().info('Deadman button released → ENABLED')
                self.set_state('enabled')
                self._recover_from_noncrit = False

    def _crit_hb_cb(self, msg):
        if msg.data:
            self._last_crit_hb = time.time()
        else:
            self.get_logger().error('Critical Issue received → DISABLED')
            self.set_state('disabled')
            self._recover_from_noncrit = False

    def _noncrit_hb_cb(self, msg):
        self._last_noncrit_hb = time.time()
        if not hasattr(self, '_noncrit_last_value'):
            self._noncrit_last_value = True
        if not hasattr(self, '_noncrit_manual_logged'):
            self._noncrit_manual_logged = False
        if not hasattr(self, '_noncrit_auto_logged'):
            self._noncrit_auto_logged = False

        if msg.data != self._noncrit_last_value:
            self._noncrit_last_value = msg.data
            if msg.data:
                self.get_logger().info('Noncritical Issue recovered')
                self.noncrit_ok = True
                self._warned_noncrit = False
                self._noncrit_manual_logged = False
                self._noncrit_auto_logged = False
                if self.current_state == 'enabled':
                    self.handle_enabled_entry()
            else:
                self.noncrit_ok = False
                if self.autonomous_mode:
                    if self.current_state == 'active':
                        self.get_logger().warn('Noncritical Issue in autonomous mode → ENABLED')
                        self.set_state('enabled')
                        self._recover_from_noncrit = True
                        self.handle_enabled_entry()
                    else:
                        self.get_logger().warn(f'Noncritical Issue received in autonomous mode stay in {self.current_state} state')
                    self._noncrit_auto_logged = True
                else:
                    self.get_logger().warn(f'Noncritical Issue received in manual mode stay in {self.current_state} state')
                    self._noncrit_manual_logged = True

    def _check_heartbeats(self):
        now = time.time()
        if now - self._last_crit_hb > self._crit_hb_to:
            if not hasattr(self, '_crit_lost_logged') or not self._crit_lost_logged:
                self.get_logger().error('Critical heartbeat lost → DISABLED')
                self._crit_lost_logged = True
            if self.autonomous_active_timer:
                self.autonomous_active_timer.cancel()
                self.autonomous_active_timer = None
            if self.current_state != 'disabled':
                self.set_state('disabled')
            self._recover_from_noncrit = False
            return
        else:
            self._crit_lost_logged = False

        if now - self._last_noncrit_hb > self._noncrit_hb_to:
            if not hasattr(self, '_noncrit_lost_logged') or not self._noncrit_lost_logged:
                self.get_logger().error('Noncritical heartbeat LOST → DISABLED')
                self._noncrit_lost_logged = True
            if self.autonomous_active_timer:
                self.autonomous_active_timer.cancel()
                self.autonomous_active_timer = None
            if self.current_state != 'disabled':
                self.set_state('disabled')
            self.noncrit_ok = False
            self._recover_from_noncrit = False
            return
        else:
            self._noncrit_lost_logged = False
            self.noncrit_ok = True
            if self._warned_noncrit:
                self.get_logger().info('Noncritical heartbeat recovered')
                self._warned_noncrit = False


def main(args=None):
    rclpy.init()
    node = RobotStateMachine()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
