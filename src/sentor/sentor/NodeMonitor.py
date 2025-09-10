#!/usr/bin/env python3
"""
Created on 20 May 2025

@author: Zhuoling Huang
"""
#####################################################################################
import time
import threading
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor

class NodeMonitor(threading.Thread):
    """
    Monitors whether a given ROS2 node is alive (and optionally autonomy-alive).

    Spins its own SingleThreadedExecutor so it doesn't interfere with the global one.
    """
    def __init__(
        self,
        target_node_name: str,
        timeout: float,
        event_callback,
        safety_critical: bool = False,
        autonomy_critical: bool = False,
        poll_rate: float = 1.0,
    ):
        super().__init__(daemon=True)
        self.target   = target_node_name
        self.timeout  = timeout
        self.event_cb = event_callback

        # flags for safety vs autonomy
        self.safety_critical   = safety_critical
        self.autonomy_critical = autonomy_critical

        # current states
        self.is_alive          = False
        self.is_autonomy_alive = False
        self._last_seen        = None

        # build a dedicated node + executor
        node_name = f"node_monitor_{self.target.replace('/', '_')}"
        self.node = Node(node_name)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self.node)

        # periodic timer to poll graph
        self.node.create_timer(1.0 / poll_rate, self._on_timer)

        # control flag for run()
        self._stop_event = threading.Event()

    def _on_timer(self):
        # check for target in graph
        names = [n for (n, ns) in self.node.get_node_names_and_namespaces()]
        now = time.time()
        if self.target in names:
            self._last_seen = now

        alive = (self._last_seen is not None) and (now - self._last_seen < self.timeout)
        if alive != self.is_alive:
            self.is_alive = alive
            lvl = 'error' if (not alive and self.safety_critical) else 'info'
            self.event_cb(f"Node {self.target} safety is {'alive' if alive else 'dead'}", lvl)

        auto_alive = alive and self.autonomy_critical
        if auto_alive != self.is_autonomy_alive:
            self.is_autonomy_alive = auto_alive
            lvl = 'error' if (not auto_alive and self.autonomy_critical) else 'info'
            self.event_cb(f"Node {self.target} autonomy is {'alive' if auto_alive else 'dead'}", lvl)

    def run(self):
        # spin only this node in its own executor
        while not self._stop_event.is_set():
            self._executor.spin_once(timeout_sec=0.1)

    def stop_monitor(self):
        # stop spinning and clean up
        self._stop_event.set()
        try:
            self.node.destroy_node()
        except Exception:
            pass
