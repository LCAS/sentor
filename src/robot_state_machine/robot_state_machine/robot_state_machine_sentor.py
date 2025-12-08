#!/usr/bin/env python3
"""
Robot State Machine

Owns the robot's runtime state and coordinates with SENTOR.

States:
  start-up  →  disabled  ↔  enabled  →  active

High-level behavior:
  • Startup: after 3s automatically goes to DISABLED.
  • Manual mode: operator controls ACTIVE via the deadman button.
  • Autonomous mode: auto-resumes to ACTIVE after 3s of clean non-critical health
    when coming from a non-critical issue (e.g., obstacle detected).
  • Any critical fault or missing critical/non critical heartbeat → DISABLED immediately.

Subscribes:
  /sentor/heartbeat_critical    (Bool)  — TRUE when all critical heartbeats are fresh.
                                        — Depending on SENTOR policy, this may publish only when healthy.
  /sentor/heartbeat_noncritical (Bool)  — TRUE/FALSE indicates non-critical health.
  /set_mode                     (String:'manual'|'autonomous')
  /set_state                    (String:'disabled'|'enabled'|'active')  — for debugging/legal transitions.
  /deadman_button               (Bool)   — operator hold in MANUAL mode.

Publishes:
  /robot_state    (String) — one of 'start-up'|'disabled'|'enabled'|'active'
  /autonomous_mode (Bool)   — TRUE in autonomous, FALSE in manual

Notes on heartbeat semantics:
  • This node uses two signals from SENTOR: the current value (TRUE/FALSE) and the
    freshness (did we recently receive any message). For critical heartbeat, if
    SENTOR is configured to go silent on failure, freshness loss is what triggers DISABLED.
    If SENTOR explicitly publishes FALSE on failure, the _crit_hb_cb() path below
    also forces DISABLED. Both paths are supported here.
"""

import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool


class RobotStateMachine(Node):
    def __init__(self):
        super().__init__('robot_state_machine')

        # --- State model ---
        self.states = ['start-up', 'disabled', 'enabled', 'active']
        self.current_state = 'start-up'

        # Flag used only for logging a later "noncritical heartbeat recovered" message in _check_heartbeats.
        self._warned_noncrit = False

        # Non-critical health and recovery intent
        self.noncrit_ok = True                 # summary health as last seen
        self._recover_from_noncrit = False     # set when we left ACTIVE due to non-critical issue
        self._last_localization_lost = False   # reserved (not used here)

        # --- Publishers ---
        self.state_pub = self.create_publisher(String, 'robot_state', 10)
        self.autonomous_pub = self.create_publisher(Bool, 'autonomous_mode', 10)

        # --- Mode management ---
        # Parameter decides initial mode (defaults to manual --> False)
        self.declare_parameter('autonomous_mode', False)
        self.autonomous_mode = self.get_parameter('autonomous_mode').value
        self.autonomous_pub.publish(Bool(data=self.autonomous_mode))

        # --- Periodic re-publish timers (1 Hz) ---
        self.create_timer(1.0, self.republish_state)
        self.create_timer(1.0, self.republish_mode)

        # Publish initial state (start-up)
        self.publish_state()

        # --- Deadman handling (MANUAL mode only) ---
        self.last_deadman = time.time()   # last time we saw a deadman message
        self.deadman_timeout = 0.5        # if ACTIVE in manual and no deadman for >0.5s → ENABLED
        self.create_timer(0.1, self._deadman_watchdog)

        # --- SENTOR summary heartbeat freshness tracking ---
        # We record the freshness of the two summary topics to detect silence
        # (e.g., if SENTOR stops publishing or network hiccups occur).
        self._last_crit_hb = time.time()
        self._last_noncrit_hb = time.time()
        self._crit_hb_to = 2.0 # 0.5
        self._noncrit_hb_to = 2.0 # 0.5

        # Subscribe to SENTOR summary topics. We use both payload value and freshness:
        #  - Critical: FALSE payload OR freshness loss ⇒ DISABLED.
        #  - Non-critical: FALSE payload ⇒ handle according to mode; freshness loss ⇒ DISABLED.
        self.create_subscription(Bool, '/safety/heartbeat', self._crit_hb_cb, 10)
        self.create_subscription(Bool, '/warning/heartbeat', self._noncrit_hb_cb, 10)
        self.create_timer(0.1, self._check_heartbeats)

        # --- Timers for startup and autonomous grace ---
        self.startup_timer = self.create_timer(3.0, self.startup_complete)  # start-up → disabled after 3s
        self.autonomous_active_timer = None  # created on demand to re-enter ACTIVE after recovery

        # --- Operator interfaces ---
        self.create_subscription(String, 'set_mode', self.set_mode_selector_callback, 10)
        self.create_subscription(String, 'set_state', self.set_state_selector_callback, 10)
        self.create_subscription(Bool, 'deadman_button', self.deadman_callback, 10)

    # --- Publish current state ---
    def publish_state(self):
        msg = String(data=self.current_state)
        self.state_pub.publish(msg)
        self.get_logger().info(f'Robot state: {self.current_state}')

    def republish_state(self):
        """Re-publish the current robot state periodically for robustness."""
        msg = String(data=self.current_state)
        self.state_pub.publish(msg)

    def republish_mode(self):
        """Re-publish the current autonomous/manual mode periodically."""
        msg = Bool(data=self.autonomous_mode)
        self.autonomous_pub.publish(msg)

    # --- State setter  ---
    def set_state(self, new_state):
        if new_state != self.current_state:
            self.current_state = new_state
            if new_state == 'enabled':
                # Reset non-critical warning latch on entry to ENABLED
                self._warned_noncrit = False
            self.publish_state()

    # After start-up timer fires, enter DISABLED
    def startup_complete(self):
        self.startup_timer.cancel()
        self.set_state('disabled')

    # --- Mode selection (manual/autonomous) ---
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

            # If mode changes while ACTIVE, fall back to ENABLED for safety
            if self.current_state == 'active':
                self.get_logger().info(f"Mode change while ACTIVE → ENABLED")
                self.set_state('enabled')
                self._recover_from_noncrit = False
                self.handle_enabled_entry()

    # --- State selector (by the operator) ---
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
                # Explicit entry to ENABLED cancels any pending auto-recovery
                self._recover_from_noncrit = False
                self.handle_enabled_entry()
        else:
            self.get_logger().warn(f"Illegal transition {self.current_state} → {req}")

    # --- On entering ENABLED, schedule auto-activate for autonomous mode ---
    def handle_enabled_entry(self):
        # Cancel any previous auto-activate timer
        if self.autonomous_active_timer:
            self.autonomous_active_timer.cancel()

        # Only arm auto-activation if we came from a non-critical issue and health is good now
        if self.autonomous_mode and self.noncrit_ok and self._recover_from_noncrit:
            # Wait 3s, then call autonomous_go_active()
            self.autonomous_active_timer = self.create_timer(3.0, self.autonomous_go_active)

    # --- Auto-transition to ACTIVE (autonomous mode) ---
    def autonomous_go_active(self):
        if (self.current_state == 'enabled'
            and self.autonomous_mode
            and self.noncrit_ok):
            # One-shot timer; cancel then enter ACTIVE
            self.autonomous_active_timer.cancel()
            self.autonomous_active_timer = None
            self.set_state('active')
            self._recover_from_noncrit = False

    # --- Deadman button input (manual mode only) ---
    def deadman_callback(self, msg):
        self.last_deadman = time.time()  # update freshness every message
        if not self.autonomous_mode:
            if self.current_state == 'enabled' and msg.data:
                self.get_logger().info('Deadman pressed → ACTIVE')
                self.set_state('active')
            elif self.current_state == 'active' and not msg.data:
                self.get_logger().info('Deadman released → ENABLED')
                self.set_state('enabled')
                self._recover_from_noncrit = False

    # Watchdog to fall back if deadman stops arriving in Manual mode and ACTIVE state
    def _deadman_watchdog(self):
        if not self.autonomous_mode and self.current_state == 'active':
            if time.time() - self.last_deadman > self.deadman_timeout:
                self.get_logger().info('Deadman button released → ENABLED')
                self.set_state('enabled')
                self._recover_from_noncrit = False

    # --- SENTOR summary callbacks ---
    def _crit_hb_cb(self, msg):
        # Update freshness timestamp on any arrival
        if msg.data:
            self._last_crit_hb = time.time()
        else:
            # If SENTOR publishes explicit FALSE for critical failure, force DISABLED.
            # (If SENTOR goes silent instead, _check_heartbeats() below will catch it.)
            self.get_logger().error('Critical Issue received → DISABLED')
            self.set_state('disabled')
            self._recover_from_noncrit = False

    def _noncrit_hb_cb(self, msg):
        # Always record freshness of the non-critical summary
        self._last_noncrit_hb = time.time()

        # Lazy-init latches used to avoid duplicate logs
        if not hasattr(self, '_noncrit_last_value'):
            self._noncrit_last_value = True
        if not hasattr(self, '_noncrit_manual_logged'):
            self._noncrit_manual_logged = False
        if not hasattr(self, '_noncrit_auto_logged'):
            self._noncrit_auto_logged = False

        # React only on value flips to reduce log noise
        if msg.data != self._noncrit_last_value:
            self._noncrit_last_value = msg.data
            if msg.data:
                # Recovery path
                self.get_logger().info('Noncritical Issue recovered')
                self.noncrit_ok = True
                self._warned_noncrit = False
                self._noncrit_manual_logged = False
                self._noncrit_auto_logged = False
                # If we are in ENABLED (after a non-critical event), consider auto-activate
                if self.current_state == 'enabled':
                    self.handle_enabled_entry()
            else:
                # New non-critical issue
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

    # --- Heartbeat freshness watchdog (covers silence from SENTOR or network drops) ---
    def _check_heartbeats(self):
        now = time.time()

        # Critical summary freshness — silence ⇒ DISABLED
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

        # Non-critical summary freshness — silence ⇒ DISABLED
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
            # This branch is reached when the summary is fresh again; optional recovery log
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