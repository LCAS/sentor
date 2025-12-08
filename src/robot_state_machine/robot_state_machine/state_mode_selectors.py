#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool

class StateModeSelectors(Node):
    """
    Provides manual or CLI control for robot state and mode.
    Publishes `robot_state` and `autonomous_mode` topics.
    """
    def __init__(self):
        super().__init__('state_mode_selectors')
        self.pub_state = self.create_publisher(String, 'set_state', 10)
        self.pub_mode  = self.create_publisher(String, 'set_mode', 10)

    def set_state(self, state: str):
        valid = ['disabled','enabled','active']
        st = state.strip().lower()
        if st in valid:
            msg = String(data=st)
            self.pub_state.publish(msg)
            self.get_logger().info(f"State set to: {st}")
        else:
            self.get_logger().warn(f"Invalid state selector: {state}")

    def set_mode(self, mode: str):
        m = mode.strip().lower()
        if m in ['manual','autonomous']:
            msg = Bool(data=(m=='autonomous'))
            self.pub_mode.publish(msg)
            self.get_logger().info(f"Mode set to: {m}")
        else:
            self.get_logger().warn(f"Invalid mode selector: {mode}")

    def keyboard_loop(self):
        # Simple CLI loop for demonstration
        while rclpy.ok():
            inp = input("Enter 's:state' or 'm:mode' (e.g. s:enabled, m:manual): ")
            if inp.startswith('s:'):
                self.set_state(inp[2:])
            elif inp.startswith('m:'):
                self.set_mode(inp[2:])
            else:
                self.get_logger().warn("Unrecognized input format.")


def main(args=None):
    rclpy.init(args=args)
    node = StateModeSelectors()
    try:
        node.keyboard_loop()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()