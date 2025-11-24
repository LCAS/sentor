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
    Guard that checks robot state and autonomous mode before allowing execution.
    
    Monitors /robot_state and /autonomous_mode topics from RobotStateMachine.
    The guard ensures these messages are recent (within update_timeout).
    
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
                 update_timeout: float = 1.0,
                 required_state: str = 'active',
                 require_autonomous_mode: bool = True):
        """
        Initialize the guard.
        
        Args:
            node: ROS2 node to use for subscriptions
            state_topic: Topic publishing robot state (String: 'start-up', 'disabled', 'enabled', 'active')
            mode_topic: Topic publishing autonomous mode flag (Bool)
            update_timeout: Maximum age of state/mode messages in seconds
            required_state: State required for autonomy (default: 'active')
            require_autonomous_mode: Whether autonomous mode must be true (default: True)
        """
        self.node = node
        self.update_timeout = Duration(seconds=update_timeout)
        self.required_state = required_state
        self.require_autonomous_mode = require_autonomous_mode
        
        self._lock = Lock()
        self._current_state = None
        self._autonomous_mode = None
        self._last_state_time = None
        self._last_mode_time = None
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
        
        self.node.get_logger().info(
            f"SentorGuard initialized: required_state='{required_state}', "
            f"update_timeout={update_timeout}s"
        )
    
    def _state_callback(self, msg):
        """Handle robot state updates."""
        with self._lock:
            self._current_state = msg.data
            self._last_state_time = self.node.get_clock().now()
            self._check_conditions()
    
    def _mode_callback(self, msg):
        """Handle autonomous mode updates."""
        with self._lock:
            self._autonomous_mode = msg.data
            self._last_mode_time = self.node.get_clock().now()
            self._check_conditions()
    
    def _check_conditions(self):
        """Check if all conditions are met."""
        now = self.node.get_clock().now()
        
        # Check if we have received state message
        if self._current_state is None or self._last_state_time is None:
            self._condition_met.clear()
            return
        
        # Check if state message is recent
        state_age = now - self._last_state_time
        if state_age > self.update_timeout:
            self._condition_met.clear()
            return
        
        # Check state value
        if self._current_state != self.required_state:
            self._condition_met.clear()
            return
        
        # Check if we have received mode message
        if self._autonomous_mode is None or self._last_mode_time is None:
            self._condition_met.clear()
            return
        
        # Check if mode message is recent
        mode_age = now - self._last_mode_time
        if mode_age > self.update_timeout:
            self._condition_met.clear()
            return
        
        # Check autonomous mode
        if self.require_autonomous_mode and not self._autonomous_mode:
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
            
            # Check state
            if self._current_state is None or self._last_state_time is None:
                return "Robot state not received"
            
            state_age = now - self._last_state_time
            if state_age > self.update_timeout:
                return f"Robot state stale ({state_age.nanoseconds / 1e9:.2f}s old)"
            
            if self._current_state != self.required_state:
                return f"State is '{self._current_state}', required '{self.required_state}'"
            
            # Check mode
            if self._autonomous_mode is None or self._last_mode_time is None:
                return "Autonomous mode not received"
            
            mode_age = now - self._last_mode_time
            if mode_age > self.update_timeout:
                return f"Autonomous mode stale ({mode_age.nanoseconds / 1e9:.2f}s old)"
            
            if self.require_autonomous_mode and not self._autonomous_mode:
                return "Autonomous mode is disabled"
            
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


def sentor_guarded(guard: SentorGuard = None, timeout: float = None):
    """
    Decorator that ensures a function only executes when guard conditions are met.
    
    This decorator can be used in two ways:
    1. With a guard instance as an argument
    2. As a method decorator in a class that has a 'guard' attribute
    
    Args:
        guard: SentorGuard instance to check (optional if used on class methods)
        timeout: Maximum time to wait for guard conditions (None = indefinite)
    
    Example:
        # Using with explicit guard
        @sentor_guarded(guard=my_guard, timeout=5.0)
        def autonomous_action():
            execute_navigation()
        
        # Using as method decorator (class must have self.guard)
        class MyNode(Node):
            def __init__(self):
                self.guard = SentorGuard(self)
            
            @sentor_guarded()
            def autonomous_action(self):
                execute_navigation()
    
    Raises:
        AutonomyGuardException: If guard conditions are not met within timeout
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get guard from arguments
            guard_instance = guard
            
            # If no guard provided, try to get it from self (for class methods)
            if guard_instance is None and len(args) > 0:
                # Check if first argument (self) has a guard attribute
                if hasattr(args[0], 'guard'):
                    guard_instance = args[0].guard
            
            # If still no guard, raise an error
            if guard_instance is None:
                raise ValueError(
                    "sentor_guarded decorator requires either a 'guard' parameter "
                    "or to be used on a method of a class with a 'guard' attribute"
                )
            
            # Check if guard conditions are met
            if not isinstance(guard_instance, SentorGuard):
                raise TypeError(
                    f"Expected SentorGuard instance, got {type(guard_instance)}"
                )
            
            # Wait for autonomy with the specified timeout
            guard_instance.guarded_wait(timeout=timeout)
            
            # Execute the function if guard conditions are met
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
