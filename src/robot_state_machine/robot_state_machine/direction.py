#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class Directions(Node):
    """
    Publishes directional commands (forward, backward, left, right, stop)
    to control the bridge_node and Arduino lights.
    """
    def __init__(self):
        super().__init__('directions_node')
        # Publish direction commands
        self.pub_direction = self.create_publisher(String, '/direction_command', 10)
        # Example timer or callback could go here; for now it's idle
        # You can integrate this with your UI or planner.

    def send_direction(self, direction: str):
        """
        Send a direction command if valid.
        direction: one of ['forward','backward','left','right','stop']
        """
        cmd = direction.strip().lower()
        msg = String()
        if cmd in ['forward','backward','left','right','stop']:
            msg.data = cmd
            self.pub_direction.publish(msg)
            self.get_logger().info(f"Direction command published: '{cmd}'")
        else:
            self.get_logger().warn(f"Invalid direction: '{cmd}'")


def main(args=None):
    rclpy.init(args=args)
    node = Directions()
    try:
        # Example usage: publish 'forward' every 2 seconds
        def timer_callback():
            node.send_direction('forward')
        node.create_timer(2.0, timer_callback)
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()