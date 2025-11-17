#!/usr/bin/env python3
"""
Simple demonstration of sentor_guard usage for Nav2 integration.

This shows how the guard can be used in application code, similar to
how the CheckAutonomyAllowed BT node uses it internally.

The pattern demonstrated here is what happens inside the behavior tree node,
but can also be used directly in application code for additional safety.

Usage:
    # Terminal 1 - Run this demo
    ros2 run sentor_guard simple_guard_demo.py
    
    # Terminal 2 - Publish test conditions
    ros2 topic pub /robot_state std_msgs/String "data: 'active'" -1
    ros2 topic pub /autonomous_mode std_msgs/Bool "data: true" -1
    ros2 topic pub /safety/heartbeat std_msgs/Bool "data: true" -r 2
    ros2 topic pub /warning/heartbeat std_msgs/Bool "data: true" -r 2
"""

import rclpy
from rclpy.node import Node
from sentor_guard import SentorGuard
import time


class SimpleGuardDemo(Node):
    """Demo node showing guard usage."""
    
    def __init__(self):
        super().__init__('simple_guard_demo')
        
        # Create a guard with default settings
        self.guard = SentorGuard(
            self,
            heartbeat_timeout=2.0,  # Allow 2 seconds for heartbeat freshness
            required_state='active'
        )
        
        self.get_logger().info('Simple Guard Demo started')
        self.get_logger().info('Waiting for safety conditions to be met...')
        self.get_logger().info('')
        self.get_logger().info('Required conditions:')
        self.get_logger().info('  - /robot_state == "active"')
        self.get_logger().info('  - /autonomous_mode == true')
        self.get_logger().info('  - /safety/heartbeat == true (fresh)')
        self.get_logger().info('  - /warning/heartbeat == true (fresh)')
        self.get_logger().info('')
        self.get_logger().info('Publish these topics to allow navigation...')
    
    def check_and_navigate(self):
        """Simulate navigation with guard checking."""
        
        # Check if autonomy is allowed (non-blocking)
        if self.guard.is_autonomy_allowed():
            self.get_logger().info('✓ Autonomy allowed - Navigation would proceed')
            return True
        else:
            reason = self.guard.get_blocking_reason()
            self.get_logger().warn(f'✗ Autonomy blocked: {reason}')
            return False
    
    def simulate_navigation(self):
        """Simulate a navigation task with continuous checking."""
        
        self.get_logger().info('\n=== Simulating Navigation Task ===')
        self.get_logger().info('This demonstrates continuous safety checking...\n')
        
        # Simulate navigation loop
        for waypoint in range(1, 6):
            self.get_logger().info(f'Navigating to waypoint {waypoint}/5...')
            
            # In real Nav2, this check happens in the behavior tree
            # via the CheckAutonomyAllowed condition node
            if not self.guard.is_autonomy_allowed():
                reason = self.guard.get_blocking_reason()
                self.get_logger().error(f'Navigation paused: {reason}')
                self.get_logger().info('Waiting for conditions to be satisfied...')
                
                # Wait for conditions with timeout
                if self.guard.wait_for_autonomy(timeout=5.0):
                    self.get_logger().info('Conditions satisfied - Resuming navigation')
                else:
                    self.get_logger().error('Timeout waiting for conditions - Aborting')
                    return False
            
            # Simulate navigation progress
            time.sleep(1.0)
            rclpy.spin_once(self, timeout_sec=0.1)
            
        self.get_logger().info('✓ Navigation complete!')
        return True


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    
    demo = SimpleGuardDemo()
    
    try:
        # Create a rate for periodic checking
        rate = demo.create_rate(1.0)  # 1 Hz
        
        navigation_started = False
        
        while rclpy.ok():
            # Periodically check and report status
            if demo.check_and_navigate():
                if not navigation_started:
                    # Once conditions are met, simulate a navigation task
                    navigation_started = True
                    demo.simulate_navigation()
                    demo.get_logger().info('\nReturning to monitoring mode...\n')
            
            rclpy.spin_once(demo, timeout_sec=0.1)
            rate.sleep()
            
    except KeyboardInterrupt:
        demo.get_logger().info('Demo stopped by user')
    finally:
        demo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
