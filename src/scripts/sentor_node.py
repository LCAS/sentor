#!/usr/bin/env python3
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)
"""
##########################################################################################
from sentor.TopicMonitor import TopicMonitor
from sentor.SafetyMonitor import SafetyMonitor
from sentor.MultiMonitor import MultiMonitor
from std_msgs.msg import String
from sentor.msg import SentorEvent
from std_srvs.srv import Empty
import rclpy
from rclpy.node import Node
import signal
import yaml
import sys
import os
import time


class SentorNode(Node):
    def __init__(self):
        super().__init__('sentor')
        
        self.topic_monitors = []
        self.declare_parameters(
            namespace='',
            parameters=[
                ('config_file', ''),
                ('safe_operation_timeout', 10.0),
                ('auto_safety_tagging', True),
                ('safety_pub_rate', 10.0),
                ('independent_tags', False)
            ]
        )

        config_file = self.get_parameter('config_file').value
        try:
            items = [yaml.safe_load(open(item, 'r')) for item in config_file.split(',')]
            self.topics = [item for sublist in items for item in sublist]
        except Exception as e:
            self.get_logger().error("No configuration file provided: %s" % e)
            self.topics = []

        # Setup services
        self.stop_srv = self.create_service(Empty, '/sentor/stop_monitor', self.stop_monitoring)
        self.start_srv = self.create_service(Empty, '/sentor/start_monitor', self.start_monitoring)

        # Setup publishers
        self.event_pub = self.create_publisher(String, '/sentor/event', 10)
        self.rich_event_pub = self.create_publisher(SentorEvent, '/sentor/rich_event', 10)
        
        # Setup monitors
        self.safety_monitor = SafetyMonitor("safe_operation", "SAFE OPERATION", 
                                          "thread_is_safe", "set_safety_tag", 
                                          self.event_callback)
        self.autonomy_monitor = SafetyMonitor("pause_autonomous_operation", 
                                            "SAFE AUTONOMOUS OPERATION", 
                                            "thread_is_auto", "set_autonomy_tag", 
                                            self.event_callback, invert=True)
        self.multi_monitor = MultiMonitor()

        self.setup_topic_monitors()
        
    def setup_topic_monitors(self):
        self.get_logger().info("Monitoring topics:")
        for i, topic in enumerate(self.topics):
            include = topic.get('include', True)
            if not include:
                continue
            
            try:
                topic_name = topic["name"]
            except Exception as e:
                self.get_logger().error("topic name is not specified for entry %s" % topic)
                continue

            rate = topic.get('rate', 0)
            N = int(topic.get('N', 0))
            signal_when = topic.get('signal_when', {})
            signal_lambdas = topic.get('signal_lambdas', [])
            processes = topic.get('execute', [])
            timeout = topic.get('timeout', 0)
            default_notifications = topic.get('default_notifications', True)

            topic_monitor = TopicMonitor(topic_name, rate, N, signal_when, 
                                       signal_lambdas, processes, timeout,
                                       default_notifications, self.event_callback, i)

            self.topic_monitors.append(topic_monitor)
            self.safety_monitor.register_monitors(topic_monitor)
            self.autonomy_monitor.register_monitors(topic_monitor)
            self.multi_monitor.register_monitors(topic_monitor)

    def start_monitoring(self, request, response):
        for topic_monitor in self.topic_monitors:
            topic_monitor.start_monitor()

        self.safety_monitor.start_monitor()
        self.autonomy_monitor.start_monitor()
        self.multi_monitor.start_monitor()

        self.get_logger().warn("sentor_node started monitoring")
        return response

    def stop_monitoring(self, request, response):
        for topic_monitor in self.topic_monitors:
            topic_monitor.stop_monitor()
            
        self.safety_monitor.stop_monitor()
        self.autonomy_monitor.stop_monitor()
        self.multi_monitor.stop_monitor()

        self.get_logger().warn("sentor_node stopped monitoring")
        return response

    def event_callback(self, string, type, msg="", nodes=[], topic=""):
        if type == "info":
            self.get_logger().info(f"{string}\n{str(msg)}")
        elif type == "warn":
            self.get_logger().warn(f"{string}\n{str(msg)}")
        elif type == "error":
            self.get_logger().error(f"{string}\n{str(msg)}")

        if self.event_pub:
            self.event_pub.publish(String(data=f"{type}: {string}"))

        if self.rich_event_pub:
            event = SentorEvent()
            event.header.stamp = self.get_clock().now().to_msg()
            event.level = {
                "info": SentorEvent.INFO,
                "warn": SentorEvent.WARN,
                "error": SentorEvent.ERROR
            }[type]
            event.message = string
            event.nodes = nodes
            event.topic = topic
            self.rich_event_pub.publish(event)

    def cleanup(self):
        for topic_monitor in self.topic_monitors:
            topic_monitor.kill_monitor()
            topic_monitor.join()

        self.safety_monitor.stop_monitor()
        self.autonomy_monitor.stop_monitor()
        self.multi_monitor.stop_monitor()
        self.get_logger().info("stopped.")


def main(args=None):
    rclpy.init(args=args)
    
    sentor_node = SentorNode()
    
    try:
        rclpy.spin(sentor_node)
    except KeyboardInterrupt:
        pass
    finally:
        sentor_node.cleanup()
        sentor_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()