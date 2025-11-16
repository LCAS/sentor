"""Tests for Python SentorGuard."""

import unittest
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from sentor_guard import SentorGuard, AutonomyGuardException
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
        
        # Publish heartbeats
        hb_msg = Bool()
        hb_msg.data = True
        self.safety_pub.publish(hb_msg)
        self.warning_pub.publish(hb_msg)
        
        # Spin to process messages
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


if __name__ == '__main__':
    unittest.main()
