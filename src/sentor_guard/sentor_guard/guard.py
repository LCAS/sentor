"""Python implementation of SentorGuard for safe autonomous operations."""

import rclpy
from rclpy.node import Node
from rclpy.time import Time, Duration
from std_msgs.msg import String, Bool
from threading import Event, Lock
import time


class AutonomyGuardException(Exception):
    """Raised when autonomy guard conditions are not met within timeout."""
    pass


class SentorGuard:
    """
    Guard that checks sentor state and heartbeat before allowing execution.
    
    Can be used as a context manager or called directly.
    
    Example:
        # As context manager
        with SentorGuard(node):
            execute_autonomous_action()
        
        # With explicit timeout
        guard = SentorGuard(node)
        if guard.wait_for_autonomy(timeout=5.0):
            execute_autonomous_action()
    """
    
    def __init__(self, node: Node, 
                 state_topic: str = '/robot_state',
                 mode_topic: str = '/autonomous_mode',
                 safety_heartbeat_topic: str = '/safety/heartbeat',
                 warning_heartbeat_topic: str = '/warning/heartbeat',
                 heartbeat_timeout: float = 1.0,
                 required_state: str = 'active',
                 require_autonomous_mode: bool = True,
                 require_safety_heartbeat: bool = True,
                 require_warning_heartbeat: bool = True):
        """
        Initialize the guard.
        
        Args:
            node: ROS2 node to use for subscriptions
            state_topic: Topic publishing robot state
            mode_topic: Topic publishing autonomous mode flag
            safety_heartbeat_topic: Topic for safety heartbeat
            warning_heartbeat_topic: Topic for warning heartbeat
            heartbeat_timeout: Maximum age of heartbeat in seconds
            required_state: State required for autonomy (e.g., 'active')
            require_autonomous_mode: Whether autonomous mode must be true
            require_safety_heartbeat: Whether safety heartbeat must be true
            require_warning_heartbeat: Whether warning heartbeat must be true
        """
        self.node = node
        self.heartbeat_timeout = Duration(seconds=heartbeat_timeout)
        self.required_state = required_state
        self.require_autonomous_mode = require_autonomous_mode
        self.require_safety_heartbeat = require_safety_heartbeat
        self.require_warning_heartbeat = require_warning_heartbeat
        
        self._lock = Lock()
        self._current_state = None
        self._autonomous_mode = None
        self._safety_heartbeat = None
        self._warning_heartbeat = None
        self._last_safety_heartbeat_time = None
        self._last_warning_heartbeat_time = None
        self._condition_met = Event()
        
        # Subscribe to state and mode topics
        self._state_sub = node.create_subscription(
            String,
            state_topic,
            self._state_callback,
            10
        )
        
        self._mode_sub = node.create_subscription(
            Bool,
            mode_topic,
            self._mode_callback,
            10
        )
        
        # Subscribe to heartbeat topics
        self._safety_heartbeat_sub = node.create_subscription(
            Bool,
            safety_heartbeat_topic,
            self._safety_heartbeat_callback,
            10
        )
        
        self._warning_heartbeat_sub = node.create_subscription(
            Bool,
            warning_heartbeat_topic,
            self._warning_heartbeat_callback,
            10
        )
        
        self.node.get_logger().info(
            f"SentorGuard initialized: required_state='{required_state}', "
            f"heartbeat_timeout={heartbeat_timeout}s"
        )
    
    def _state_callback(self, msg):
        """Handle robot state updates."""
        with self._lock:
            self._current_state = msg.data
            self._check_conditions()
    
    def _mode_callback(self, msg):
        """Handle autonomous mode updates."""
        with self._lock:
            self._autonomous_mode = msg.data
            self._check_conditions()
    
    def _safety_heartbeat_callback(self, msg):
        """Handle safety heartbeat updates."""
        with self._lock:
            self._safety_heartbeat = msg.data
            self._last_safety_heartbeat_time = self.node.get_clock().now()
            self._check_conditions()
    
    def _warning_heartbeat_callback(self, msg):
        """Handle warning heartbeat updates."""
        with self._lock:
            self._warning_heartbeat = msg.data
            self._last_warning_heartbeat_time = self.node.get_clock().now()
            self._check_conditions()
    
    def _check_conditions(self):
        """Check if all conditions are met."""
        now = self.node.get_clock().now()
        
        # Check state
        if self._current_state != self.required_state:
            self._condition_met.clear()
            return
        
        # Check autonomous mode
        if self.require_autonomous_mode and not self._autonomous_mode:
            self._condition_met.clear()
            return
        
        # Check safety heartbeat
        if self.require_safety_heartbeat:
            if self._safety_heartbeat is None or not self._safety_heartbeat:
                self._condition_met.clear()
                return
            
            if self._last_safety_heartbeat_time is None:
                self._condition_met.clear()
                return
            
            age = now - self._last_safety_heartbeat_time
            if age > self.heartbeat_timeout:
                self._condition_met.clear()
                return
        
        # Check warning heartbeat
        if self.require_warning_heartbeat:
            if self._warning_heartbeat is None or not self._warning_heartbeat:
                self._condition_met.clear()
                return
            
            if self._last_warning_heartbeat_time is None:
                self._condition_met.clear()
                return
            
            age = now - self._last_warning_heartbeat_time
            if age > self.heartbeat_timeout:
                self._condition_met.clear()
                return
        
        # All conditions met
        self._condition_met.set()
    
    def is_autonomy_allowed(self) -> bool:
        """
        Check if autonomy is currently allowed (non-blocking).
        
        Returns:
            True if all guard conditions are satisfied, False otherwise
        """
        with self._lock:
            self._check_conditions()  # Recheck heartbeat age
            return self._condition_met.is_set()
    
    def get_blocking_reason(self) -> str:
        """
        Get human-readable reason why autonomy is blocked.
        
        Returns:
            String describing why autonomy is not allowed
        """
        with self._lock:
            now = self.node.get_clock().now()
            
            if self._current_state != self.required_state:
                return f"State is '{self._current_state}', required '{self.required_state}'"
            
            if self.require_autonomous_mode and not self._autonomous_mode:
                return "Autonomous mode is disabled"
            
            if self.require_safety_heartbeat:
                if self._safety_heartbeat is None or not self._safety_heartbeat:
                    return "Safety heartbeat is unhealthy or not received"
                
                if self._last_safety_heartbeat_time:
                    age = now - self._last_safety_heartbeat_time
                    if age > self.heartbeat_timeout:
                        return f"Safety heartbeat stale ({age.nanoseconds / 1e9:.2f}s old)"
            
            if self.require_warning_heartbeat:
                if self._warning_heartbeat is None or not self._warning_heartbeat:
                    return "Warning heartbeat is unhealthy or not received"
                
                if self._last_warning_heartbeat_time:
                    age = now - self._last_warning_heartbeat_time
                    if age > self.heartbeat_timeout:
                        return f"Warning heartbeat stale ({age.nanoseconds / 1e9:.2f}s old)"
            
            return "Unknown reason"
    
    def wait_for_autonomy(self, timeout: float = None) -> bool:
        """
        Wait until autonomy is allowed.
        
        Args:
            timeout: Maximum time to wait in seconds. None for indefinite.
            
        Returns:
            True if autonomy is allowed, False if timeout occurred
        """
        start_time = time.time()
        
        while rclpy.ok():
            if self.is_autonomy_allowed():
                return True
            
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    reason = self.get_blocking_reason()
                    self.node.get_logger().warn(
                        f"Autonomy not granted within {timeout}s: {reason}"
                    )
                    return False
            
            # Spin once to process callbacks
            rclpy.spin_once(self.node, timeout_sec=0.1)
            
        return False
    
    def __enter__(self):
        """Context manager entry - waits indefinitely by default."""
        if not self.wait_for_autonomy():
            raise AutonomyGuardException("Autonomy not allowed and node is shutting down")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return False
    
    def guarded_wait(self, timeout: float = None):
        """
        Wait for autonomy with timeout, raising exception on failure.
        
        Args:
            timeout: Maximum time to wait. None for indefinite.
            
        Raises:
            AutonomyGuardException: If timeout occurs
        """
        if not self.wait_for_autonomy(timeout):
            reason = self.get_blocking_reason()
            if timeout:
                raise AutonomyGuardException(
                    f"Autonomy not granted within {timeout}s timeout: {reason}"
                )
            else:
                raise AutonomyGuardException(
                    f"Autonomy not allowed: {reason}"
                )
