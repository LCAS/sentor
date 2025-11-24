"""Tests for Python SentorGuard."""

import unittest
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from sentor_guard import SentorGuard, AutonomyGuardException, sentor_guarded
import time


class TestSentorGuard(unittest.TestCase):
    """Test cases for SentorGuard."""
    
    @classmethod
    def setUpClass(cls):
        """Initialize ROS."""
        rclpy.init()
    
    @classmethod
    def tearDownClass(cls):
        """Shutdown ROS."""
        rclpy.shutdown()
    
    def setUp(self):
        """Set up test fixtures."""
        self.node = Node('test_guard_node')
        self.guard = SentorGuard(self.node, update_timeout=0.5)
        
        # Create test publishers
        self.state_pub = self.node.create_publisher(String, '/robot_state', 10)
        self.mode_pub = self.node.create_publisher(Bool, '/autonomous_mode', 10)
        
        time.sleep(0.1)  # Allow subscriptions to connect
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.node.destroy_node()
    
    def test_all_conditions_met(self):
        """Test that guard allows when all conditions are met."""
        # Publish required state
        msg = String()
        msg.data = 'active'
        self.state_pub.publish(msg)
        
        # Publish autonomous mode
        mode_msg = Bool()
        mode_msg.data = True
        self.mode_pub.publish(mode_msg)
        
        # Spin to process messages
        for _ in range(3):
            rclpy.spin_once(self.node, timeout_sec=0.1)
        
        # Check that autonomy is allowed
        self.assertTrue(self.guard.is_autonomy_allowed())
    
    def test_wrong_state_blocks(self):
        """Test that wrong state blocks autonomy."""
        msg = String()
        msg.data = 'paused'
        self.state_pub.publish(msg)
        
        rclpy.spin_once(self.node, timeout_sec=0.1)
        
        self.assertFalse(self.guard.is_autonomy_allowed())
        self.assertIn("State is", self.guard.get_blocking_reason())
    
    def test_mode_disabled_blocks(self):
        """Test that disabled autonomous mode blocks autonomy."""
        # Set valid state
        state_msg = String()
        state_msg.data = 'active'
        self.state_pub.publish(state_msg)
        
        # Set mode to false
        mode_msg = Bool()
        mode_msg.data = False
        self.mode_pub.publish(mode_msg)
        
        rclpy.spin_once(self.node, timeout_sec=0.1)
        
        self.assertFalse(self.guard.is_autonomy_allowed())
        self.assertIn("mode", self.guard.get_blocking_reason().lower())
    
    def test_timeout_exception(self):
        """Test that timeout raises exception."""
        with self.assertRaises(AutonomyGuardException):
            self.guard.guarded_wait(timeout=0.1)


class TestSentorGuardDecorator(unittest.TestCase):
    """Test cases for @sentor_guarded decorator."""
    
    @classmethod
    def setUpClass(cls):
        """Initialize ROS."""
        if not rclpy.ok():
            rclpy.init()
    
    def setUp(self):
        """Set up test fixtures."""
        self.node = Node('test_decorator_node')
        self.guard = SentorGuard(self.node, heartbeat_timeout=0.5)
        
        # Create test publishers
        self.state_pub = self.node.create_publisher(String, '/robot_state', 10)
        self.mode_pub = self.node.create_publisher(Bool, '/autonomous_mode', 10)
        self.safety_pub = self.node.create_publisher(Bool, '/safety/heartbeat', 10)
        self.warning_pub = self.node.create_publisher(Bool, '/warning/heartbeat', 10)
        
        time.sleep(0.1)  # Allow subscriptions to connect
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.node.destroy_node()
    
    def _publish_all_conditions_met(self):
        """Helper to publish all conditions as met."""
        state_msg = String()
        state_msg.data = 'active'
        self.state_pub.publish(state_msg)
        
        mode_msg = Bool()
        mode_msg.data = True
        self.mode_pub.publish(mode_msg)
        
        # Spin to process messages
        for _ in range(3):
            rclpy.spin_once(self.node, timeout_sec=0.1)
    
    def test_decorator_with_timeout_blocks(self):
        """Test that decorator raises exception on timeout."""
        # Create a test class with guard attribute
        class TestClass:
            def __init__(self, guard):
                self.guard = guard
                self.called = False
            
            @sentor_guarded(timeout=0.1)
            def guarded_method(self):
                self.called = True
        
        test_obj = TestClass(self.guard)
        
        # Should raise exception since conditions are not met
        with self.assertRaises(AutonomyGuardException):
            test_obj.guarded_method()
        
        # Method should not have been called
        self.assertFalse(test_obj.called)
    
    def test_decorator_allows_when_conditions_met(self):
        """Test that decorator allows execution when conditions are met."""
        # Publish all conditions as met
        self._publish_all_conditions_met()
        
        # Create a test class with guard attribute
        class TestClass:
            def __init__(self, guard):
                self.guard = guard
                self.called = False
            
            @sentor_guarded(timeout=1.0)
            def guarded_method(self):
                self.called = True
                return "success"
        
        test_obj = TestClass(self.guard)
        
        # Should execute successfully
        result = test_obj.guarded_method()
        
        # Method should have been called
        self.assertTrue(test_obj.called)
        self.assertEqual(result, "success")
    
    def test_decorator_with_explicit_guard(self):
        """Test decorator with explicit guard parameter."""
        self._publish_all_conditions_met()
        
        called = [False]  # Use list to capture in closure
        
        @sentor_guarded(guard=self.guard, timeout=1.0)
        def standalone_function():
            called[0] = True
            return "executed"
        
        result = standalone_function()
        self.assertTrue(called[0])
        self.assertEqual(result, "executed")
    
    def test_decorator_without_guard_raises_error(self):
        """Test that decorator raises ValueError when no guard available."""
        @sentor_guarded(timeout=0.1)
        def no_guard_function():
            pass
        
        # Should raise ValueError since no guard is available
        with self.assertRaises(ValueError):
            no_guard_function()


if __name__ == '__main__':
    unittest.main()
