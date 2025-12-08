#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool, String


class JoyStateBridge(Node):
    """
    Joystick to Robot State Bridge Node

    This node maps joystick inputs to robot mode and state control topics used
    by the RobotStateMachine.

    Features:
        - Deadman handle for manual mode (continuous press to allow movement)
        - Mode toggle buttons (manual / autonomous)
        - Dual-purpose activate button:
            • In manual mode: only DISABLED → ENABLED
            • In autonomous mode: DISABLED → ENABLED, ENABLED → ACTIVE

    Subscriptions:
        /joy (sensor_msgs/Joy)          - Joystick inputs
        /robot_state (std_msgs/String)  - Current robot state (disabled, enabled, active)
        /autonomous_mode (std_msgs/Bool) [optional] - Tracks current mode

    Publications:
        /deadman_button (std_msgs/Bool) - Deadman handle status
        /set_mode (std_msgs/String)     - Command to switch robot mode
        /set_state (std_msgs/String)    - Command to change robot state
    """

    def __init__(self):
        super().__init__('joy_robot_state_machine')

        # === BUTTON MAPPINGS ===
        # Configure according to your joystick layout.
        self.deadman_button = 4       # LB (Left bumper) - hold for manual movement
        self.manual_mode_button = 2   # X button - switch to manual mode
        self.auto_mode_button = 3     # Y button - switch to autonomous mode
        self.activate_button = 5      # RB (Right bumper) - dual-purpose enable/activate

        # Track last button states to detect rising edge events
        self.last_buttons = []

        # Track robot's current state for logic (disabled, enabled, active)
        self.current_robot_state = 'disabled'

        # Track autonomous/manual mode
        self.autonomous_mode = False

        # === Publishers ===
        self.deadman_pub = self.create_publisher(Bool, 'deadman_button', 10)
        self.set_mode_pub = self.create_publisher(String, 'set_mode', 10)
        self.set_state_pub = self.create_publisher(String, 'set_state', 10)

        # === Subscribers ===
        self.create_subscription(Joy, 'joy', self.joy_callback, 10)
        self.create_subscription(String, 'robot_state', self.robot_state_callback, 10)
        self.create_subscription(Bool, 'autonomous_mode', self.autonomous_mode_callback, 10)

        self.get_logger().info("JoyStateBridge node started. Listening for joystick input...")

    def robot_state_callback(self, msg: String):
        """
        Callback to track current robot state.
        Used to decide behavior of the dual-purpose activate button.
        """
        self.current_robot_state = msg.data.lower()

    def autonomous_mode_callback(self, msg: Bool):
        """
        Callback to track whether robot is in autonomous or manual mode.
        Used to modify activate button behavior in manual mode.
        """
        self.autonomous_mode = msg.data

    def joy_callback(self, msg: Joy):
        """
        Callback for /joy topic.
        Processes joystick buttons and publishes commands to RobotStateMachine.
        """
        # Initialize last button states on first message
        if not self.last_buttons:
            self.last_buttons = [0] * len(msg.buttons)

        # --- Deadman handle (continuous hold) ---
        deadman_pressed = bool(msg.buttons[self.deadman_button])
        self.deadman_pub.publish(Bool(data=deadman_pressed))

        # --- Mode toggle buttons (edge-triggered) ---
        if self._button_pressed(self.manual_mode_button, msg):
            self.get_logger().info("Manual mode button pressed → MANUAL")
            self.set_mode_pub.publish(String(data='manual'))

        if self._button_pressed(self.auto_mode_button, msg):
            self.get_logger().info("Autonomous mode button pressed → AUTONOMOUS")
            self.set_mode_pub.publish(String(data='autonomous'))

        # --- Dual-purpose activate button ---
        if self._button_pressed(self.activate_button, msg):
            if not self.autonomous_mode:
                # Manual mode: only allow DISABLED → ENABLED
                if self.current_robot_state == 'disabled':
                    self.get_logger().info("Manual mode: Button pressed → DISABLED → ENABLED")
                    self.set_state_pub.publish(String(data='enabled'))
                else:
                    self.get_logger().info(f"Manual mode: Button pressed → Current state: {self.current_robot_state}, no action")
            else:
                # Autonomous mode: full logic (DISABLED → ENABLED, ENABLED → ACTIVE)
                if self.current_robot_state == 'disabled':
                    self.get_logger().info("Autonomous mode: Button pressed → DISABLED → ENABLED")
                    self.set_state_pub.publish(String(data='enabled'))
                elif self.current_robot_state == 'enabled':
                    self.get_logger().info("Autonomous mode: Button pressed → ENABLED → ACTIVE")
                    self.set_state_pub.publish(String(data='active'))
                else:
                    self.get_logger().info(f"Autonomous mode: Button pressed → Current state: {self.current_robot_state}, no action")

        # Update last button states for edge detection
        self.last_buttons = msg.buttons

    def _button_pressed(self, index, msg):
        """
        Detect rising edge of a button press.
        Returns True if button is currently pressed and was not pressed in the previous message.
        """
        return msg.buttons[index] and not self.last_buttons[index]


def main(args=None):
    """
    Entry point for the JoyStateBridge node.
    Initializes ROS2, spins the node, and cleans up on shutdown.
    """
    rclpy.init(args=args)
    node = JoyStateBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
