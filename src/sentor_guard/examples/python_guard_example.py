#!/usr/bin/env python3
"""Example usage of Python SentorGuard."""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sentor_guard import SentorGuard, AutonomyGuardException, sentor_guarded


class GuardedNavigationNode(Node):
    """Example node demonstrating SentorGuard usage patterns."""
    
    def __init__(self):
        super().__init__('guarded_navigation_example')
        
        # Initialize guard
        self.guard = SentorGuard(
            self,
            required_state='active',
            heartbeat_timeout=1.0,
            require_autonomous_mode=True,
            require_safety_heartbeat=True,
            require_warning_heartbeat=True
        )
        
        # Create publisher
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Create timer for periodic action
        self.timer = self.create_timer(0.1, self.timer_callback)
        
        self.get_logger().info("Guarded navigation node started")
    
    def timer_callback(self):
        """Periodic callback - only publishes if guard allows."""
        if self.guard.is_autonomy_allowed():
            # Autonomy allowed, publish command
            msg = Twist()
            msg.linear.x = 0.5
            self.cmd_vel_pub.publish(msg)
            self.get_logger().debug("Published cmd_vel")
        else:
            # Not allowed, log reason
            reason = self.guard.get_blocking_reason()
            self.get_logger().debug(f"Navigation blocked: {reason}")
    
    def execute_mission(self):
        """Execute a mission with timeout."""
        try:
            # Wait up to 10 seconds for autonomy
            self.guard.guarded_wait(timeout=10.0)
            
            # Proceed with mission
            self.get_logger().info("Starting mission")
            self.run_mission_steps()
            
        except AutonomyGuardException as e:
            self.get_logger().error(f"Mission aborted: {e}")
    
    def run_mission_steps(self):
        """Placeholder for mission execution."""
        self.get_logger().info("Running mission steps...")
    
    def critical_action(self):
        """Critical action that must wait indefinitely."""
        with self.guard:
            self.get_logger().info("Executing critical action")
            # This code only runs when guard conditions are met
            self.perform_action()
    
    def perform_action(self):
        """Placeholder for action execution."""
        self.get_logger().info("Performing action...")
    
    @sentor_guarded()
    def decorator_example_no_timeout(self):
        """Example using decorator without timeout (waits indefinitely)."""
        self.get_logger().info("Decorator example: executing guarded action")
        msg = Twist()
        msg.linear.x = 1.0
        self.cmd_vel_pub.publish(msg)
    
    @sentor_guarded(timeout=5.0)
    def decorator_example_with_timeout(self):
        """Example using decorator with timeout."""
        self.get_logger().info("Decorator example with timeout: executing guarded action")
        msg = Twist()
        msg.linear.x = 0.8
        self.cmd_vel_pub.publish(msg)


def main():
    """Main entry point."""
    rclpy.init()
    node = GuardedNavigationNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
