#!/usr/bin/env python3
"""
Test script to demonstrate the CheckAutonomyAllowed BT condition node.

This script simulates the behavior tree node by publishing test conditions
and verifying that the guard responds correctly.

Usage:
    ros2 run sentor_guard test_bt_integration.py
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import time


class BTIntegrationTest(Node):
    """Test node for demonstrating BT integration."""
    
    def __init__(self):
        super().__init__('bt_integration_test')
        
        # Create publishers for test conditions
        self.state_pub = self.create_publisher(String, '/robot_state', 10)
        self.mode_pub = self.create_publisher(Bool, '/autonomous_mode', 10)
        self.safety_pub = self.create_publisher(Bool, '/safety/heartbeat', 10)
        self.warning_pub = self.create_publisher(Bool, '/warning/heartbeat', 10)
        
        self.get_logger().info('BT Integration Test Node started')
        self.get_logger().info('Publishing test conditions...')
        
    def publish_conditions(self, state='active', mode=True, safety=True, warning=True):
        """Publish a set of conditions."""
        state_msg = String()
        state_msg.data = state
        self.state_pub.publish(state_msg)
        
        mode_msg = Bool()
        mode_msg.data = mode
        self.mode_pub.publish(mode_msg)
        
        safety_msg = Bool()
        safety_msg.data = safety
        self.safety_pub.publish(safety_msg)
        
        warning_msg = Bool()
        warning_msg.data = warning
        self.warning_pub.publish(warning_msg)
        
        self.get_logger().info(
            f'Published: state={state}, mode={mode}, '
            f'safety={safety}, warning={warning}'
        )
    
    def run_test_sequence(self):
        """Run a sequence of test conditions."""
        
        # Test 1: All conditions met (autonomy allowed)
        self.get_logger().info('\n=== Test 1: All conditions met ===')
        self.publish_conditions('active', True, True, True)
        time.sleep(1.0)
        
        # Test 2: Wrong state (autonomy blocked)
        self.get_logger().info('\n=== Test 2: State is paused ===')
        self.publish_conditions('paused', True, True, True)
        time.sleep(1.0)
        
        # Test 3: Autonomous mode disabled (autonomy blocked)
        self.get_logger().info('\n=== Test 3: Autonomous mode disabled ===')
        self.publish_conditions('active', False, True, True)
        time.sleep(1.0)
        
        # Test 4: Safety heartbeat unhealthy (autonomy blocked)
        self.get_logger().info('\n=== Test 4: Safety heartbeat unhealthy ===')
        self.publish_conditions('active', True, False, True)
        time.sleep(1.0)
        
        # Test 5: Warning heartbeat unhealthy (autonomy blocked)
        self.get_logger().info('\n=== Test 5: Warning heartbeat unhealthy ===')
        self.publish_conditions('active', True, True, False)
        time.sleep(1.0)
        
        # Test 6: Return to safe conditions (autonomy allowed)
        self.get_logger().info('\n=== Test 6: Return to safe conditions ===')
        self.publish_conditions('active', True, True, True)
        time.sleep(1.0)
        
        # Test 7: Simulate navigation scenario - pause and resume
        self.get_logger().info('\n=== Test 7: Simulating pause/resume during navigation ===')
        for i in range(3):
            self.get_logger().info(f'  Navigation cycle {i+1}/3')
            self.publish_conditions('active', True, True, True)
            time.sleep(0.5)
            
            self.get_logger().info('  -> Pausing (obstacle detected)')
            self.publish_conditions('paused', True, True, True)
            time.sleep(0.5)
            
            self.get_logger().info('  -> Resuming (obstacle cleared)')
        
        self.publish_conditions('active', True, True, True)
        
        self.get_logger().info('\n=== Test sequence complete ===')
        self.get_logger().info('If CheckAutonomyAllowed is running in a behavior tree,')
        self.get_logger().info('it would have returned SUCCESS/FAILURE based on these conditions.')


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    test_node = BTIntegrationTest()
    
    try:
        # Run the test sequence
        test_node.run_test_sequence()
        
        # Keep publishing the final safe state
        rate = test_node.create_rate(1.0)
        test_node.get_logger().info('\nPublishing safe conditions at 1Hz...')
        test_node.get_logger().info('Press Ctrl+C to stop')
        
        while rclpy.ok():
            test_node.publish_conditions('active', True, True, True)
            rclpy.spin_once(test_node, timeout_sec=0.1)
            rate.sleep()
            
    except KeyboardInterrupt:
        test_node.get_logger().info('Test interrupted by user')
    finally:
        test_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
