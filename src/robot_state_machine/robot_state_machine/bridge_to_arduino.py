#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool, Float32
from serial import Serial, SerialException
import time
import sys


class BridgeToArduino(Node):
    def __init__(self):
        super().__init__('bridge_node')

        # --- Internal state from ROS ---
        self.current_state = 'disabled'
        self.e_stop_input = False
        self.autonomous_mode = False

        self.serial_failure_count = 0
        self.serial_failure_limit = 2  # Number of failures before shutdown


        # --- Serial Setup ---
        self.declare_parameter('arduino_port', '/dev/ttyACM0')
        port = self.get_parameter('arduino_port').value
        try:
            self.ser = Serial(port, baudrate=57600, timeout=0.1)
        except SerialException as e:
            self.get_logger().error(f"Serial init failed: {e}")
            rclpy.shutdown()
            return

        self.wait_for_arduino()

        # --- ROS Subscriptions (inputs) ---
        self.create_subscription(String, 'robot_state', self._cb_state, 10)
        self.create_subscription(String, '/e_stop/status', self._cb_estop, 10)
        self.create_subscription(Bool, 'autonomous_mode', self._cb_mode, 10)
        self.create_subscription(String, '/direction_command', self._cb_direction, 10)

        # --- ROS Publishers (outputs) ---
        self.pub_weight = self.create_publisher(Float32, 'han/balance_data', 10)
        self.pub_estop = self.create_publisher(Bool, 'estop_pressed', 10)
        self.pub_collision = self.create_publisher(Bool, 'collision_detected', 10)
        self.pub_hb = self.create_publisher(Bool, 'heartbeat_ok', 10)
        self.pub_bridge = self.create_publisher(Bool, 'arduino_bridge_alive', 10)
        self.dir_feedback = self.create_publisher(String, '/direction_feedback', 10)

        # --- Timeout tracking for Arduino connection ---
        self.last_arduino_msg_time = time.time()
        self.arduino_timeout = 1.0  # seconds
        self.create_timer(0.2, self._check_arduino_timeout)

        # --- Periodic I/O with Arduino ---
        self.create_timer(0.1, self._serial_io)

    def wait_for_arduino(self, timeout=5.0):
        start = time.time()
        while True:
            if self.ser.in_waiting:
                line = self.ser.readline().decode(errors='ignore').strip()
                if 'Arduino is ready' in line:
                    self.get_logger().info('Arduino is ready')
                    break
            if time.time() - start > timeout:
                self.get_logger().warn('Timeout waiting for Arduino. Proceeding...')
                break

    def _cb_state(self, msg: String):
        self.current_state = msg.data

    def _cb_estop(self, msg: Bool):
        self.e_stop_input = msg.data

    def _cb_mode(self, msg: Bool):
        self.autonomous_mode = msg.data

    def _cb_direction(self, msg: String):
        cmd = msg.data.strip().lower()
        if cmd in ['forward', 'backward', 'left', 'right', 'stop']:
            serial_cmd = f"<direction,{cmd}>"
            try:
                self.ser.write(serial_cmd.encode())
                self.dir_feedback.publish(String(data=f"sent '{serial_cmd}'"))
            except Exception as e:
                self.get_logger().warn(f"Direction send failed: {e}")
                self.dir_feedback.publish(String(data="Serial write failed"))
        else:
            self.dir_feedback.publish(String(data=f"unknown direction '{cmd}'"))

    def _serial_io(self):
        try:
            cmd = f"<{self.current_state},{int(self.e_stop_input)},{int(self.autonomous_mode)}>"
            self.ser.write(cmd.encode())

            self.last_arduino_msg_time = time.time()
            self.serial_failure_count = 0  # Reset on success

            raw = self.ser.readline().decode(errors='ignore').strip('<>\r\n')
            if raw.startswith('Msg 1'):
                parts = raw.split()
                if 'Weight' in parts:
                    w = float(parts[parts.index('Weight') + 1])
                    self.pub_weight.publish(Float32(data=round(w, 2)))

                est = parts[parts.index('EStop') + 1] == '1'
                bf = parts[parts.index('BumperFront') + 1] == '1'
                br = parts[parts.index('BumperRear') + 1] == '1'
                if (bf or br) and est:
                    est = False
                self.pub_estop.publish(Bool(data=est))
                self.pub_collision.publish(Bool(data=(bf or br)))
                self.pub_hb.publish(Bool(data=True))

        except Exception as e:
            self.serial_failure_count += 1
            self.get_logger().warn(f"SerialException ({self.serial_failure_count}): {e}")
            self.pub_bridge.publish(Bool(data=False))

            if self.serial_failure_count >= self.serial_failure_limit:
                self.get_logger().error("Arduino disconnected — shutting down bridge node.")
                sys.exit("Bridge node exited due to Arduino disconnect.")
                rclpy.shutdown()
                
    def _check_arduino_timeout(self):
        elapsed = time.time() - self.last_arduino_msg_time
        if elapsed > self.arduino_timeout:
            self.pub_bridge.publish(Bool(data=False))
        else:
            self.pub_bridge.publish(Bool(data=True))


def main(args=None):
    rclpy.init(args=args)
    node = BridgeToArduino()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
