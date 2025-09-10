#!/usr/bin/env python3
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)

Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang
"""
#####################################################################################
from threading import Thread, Event, Lock
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sentor.ROSTopicFilter import ROSTopicFilter
from sentor.ROSTopicHz     import ROSTopicHz
from sentor.ROSTopicPub    import ROSTopicPub
from sentor.Executor       import Executor

class TopicMonitor(Thread):
    def debug(self, msg):
        if getattr(self, 'enable_internal_logs', False) and hasattr(self, 'node'):
            self.node.get_logger().info(msg)

    def __init__(
        self,
        topic_name,
        msg_type,
        qos_profile,
        rate,
        N,
        signal_when_config,
        signal_lambdas_config,
        processes,
        timeout,
        default_notifications,
        event_callback,
        thread_num,
        enable_internal_logs=True
    ):
        super().__init__(daemon=True)
        self.topic_name            = topic_name
        self.msg_type              = msg_type
        self.qos_profile           = qos_profile
        self.rate                  = rate
        self.N                     = N
        self.signal_when_config    = signal_when_config
        self.signal_lambdas_config = signal_lambdas_config
        self.processes             = processes
        self.timeout               = timeout if timeout>0 else 0.1
        self.default_notifications = default_notifications
        self._event_callback       = event_callback
        self.thread_num            = thread_num
        self.enable_internal_logs  = enable_internal_logs

        # internal state
        self._stop_event   = Event()
        self._lock         = Lock()
        self.conditions    = {}
        self.sat_expr_timer= {}
        self.is_alive      = False
        self.is_autonomy_alive = False

        # last‐message timestamp for any‐message callback
        self._last_msg_time = time.time()

        # ROS node for this monitor
        self.node = Node(f"topic_monitor_{thread_num}")
        self.debug(f"[TopicMonitor] Created for {self.topic_name}")

        # fallback QoS
        if self.qos_profile is None:
            self.node.get_logger().warn(f"[TopicMonitor] No QoS for {self.topic_name}, using fallback")
            self.qos_profile = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10
            )

        # thread‐safe executor for any “processes”
        self.executor = Executor(processes, event_callback) if processes else None

        
        # Build self.signal_when_cfg and seed self.conditions for “signal_when”
        self.process_signal_config()
        # ------------------------------------------------------------------

        # frequency monitoring
        self.hz_monitor = ROSTopicHz(self.node, self.topic_name, window_size=1000, throttle_val=self.N)
        self.hz_monitor.start_monitoring(self.msg_type, self.qos_profile)

        # periodic status checks
        self.node.create_timer(5.0, self.log_hz_stats)
        self.node.create_timer(1.0, self.check_not_published)
        self.node.create_timer(1.0, self._check_alive_status)
        self.node.create_timer(1.0, self._check_autonomy_status)

        # subscribe to update “last_msg_time”
        self.node.create_subscription(
            self.msg_type,
            self.topic_name,
            self._on_any_msg,
            self.qos_profile
        )

        # “published”‐condition via ROSTopicPub
        if self.signal_when_cfg.get("signal_when","").lower() == "published":
            self.debug(f"Setting up ROSTopicPub for {self.topic_name}")
            pubm = ROSTopicPub(
                node=self.node,
                topic_name=self.topic_name,
                msg_type=self.msg_type,
                qos_profile=self.qos_profile,
                throttle_val=1
            )
            pubm.register_published_cb(self.published_cb)

        # per‐lambda filters
        for lam in self.signal_lambdas_config:
            cfg = self.process_lambda_config(lam)
            key = cfg["original_expr"]
            self.conditions[key] = {
                "satisfied": False,
                "safety_critical":   cfg["safety_critical"],
                "autonomy_critical": cfg["autonomy_critical"],
                "tags": cfg.get("tags", []),
            }
            fm = ROSTopicFilter(self.node, self.topic_name, cfg["expr"], cfg, throttle_val=self.N)
            fm.register_satisfied_cb(self.lambda_satisfied_cb)
            fm.register_unsatisfied_cb(self.lambda_unsatisfied_cb)

    def process_signal_config(self):
        """Initialize self.signal_when_cfg & seed self.conditions for the ‘signal_when’ check."""
        cfg = self.signal_when_config or {}
        self.signal_when_cfg = {
            "signal_when":       cfg.get("condition", ""),
            "timeout":           max(cfg.get("timeout", self.timeout), 0.1),
            "safety_critical":   cfg.get("safety_critical", False),
            "autonomy_critical": cfg.get("autonomy_critical", False),
            "default_notifications": cfg.get("default_notifications", self.default_notifications),
            "tags": cfg.get("tags", []),
        }
        if self.signal_when_cfg["signal_when"]:
            key = self.signal_when_cfg["signal_when"]
            self.conditions[key] = {"satisfied": False, **self.signal_when_cfg}

    def process_lambda_config(self, lam):
        return {
            "expr": lam["expression"],
            "original_expr": lam["expression"],
            "timeout": max(lam.get("timeout", self.timeout), 0.1),
            "safety_critical":   lam.get("safety_critical", False),
            "autonomy_critical": lam.get("autonomy_critical", False),
            "process_indices":   lam.get("process_indices", []),
        }

    def _on_any_msg(self, msg):
        self._last_msg_time = time.time()

    def _check_alive_status(self):
        stats = self.hz_monitor.get_hz() or []
        rate = stats[0] if stats else 0.0
        rate_ok = rate >= self.rate
        # require ALL safety_critical checks
        crit = [k for k,v in self.conditions.items() if v.get("safety_critical")]
        lamb_ok = all(self.conditions[k]["satisfied"] for k in crit) if crit else True
        alive = rate_ok and lamb_ok
        self.node.get_logger().info(f"[LIVENESS] {self.topic_name}: rate={rate:.2f}/{self.rate}, lambdas={crit} all={lamb_ok}")
        self.is_alive = alive

    def _check_autonomy_status(self):
        stats = self.hz_monitor.get_hz() or []
        rate = stats[0] if stats else 0.0
        rate_ok = rate >= self.rate
        crit = [k for k,v in self.conditions.items() if v.get("autonomy_critical")]
        lamb_ok = all(self.conditions[k]["satisfied"] for k in crit) if crit else True
        alive = rate_ok and lamb_ok
        self.is_autonomy_alive = alive

    def published_cb(self, msg):
        if "published" in self.conditions:
            self.conditions["published"]["satisfied"] = True

    def lambda_satisfied_cb(self, expr, msg, cfg):
        with self._lock:
            if not self.conditions[expr]["satisfied"]:
                self.conditions[expr]["satisfied"] = True

    def lambda_unsatisfied_cb(self, expr):
        with self._lock:
            self.conditions[expr]["satisfied"] = False

    def check_not_published(self):
        if self.signal_when_cfg.get("signal_when","")=="not published":
            stats = self.hz_monitor.get_hz()
            if stats is None and not self.conditions["not published"]["satisfied"]:
                self.conditions["not published"]["satisfied"] = True
                if self.signal_when_cfg["default_notifications"]:
                    lvl = "error" if self.signal_when_cfg["safety_critical"] else "warn"
                    self._event_callback(f"Topic {self.topic_name} not published", lvl)

    def log_hz_stats(self):
        stats = self.hz_monitor.get_hz()
        if stats:
            rate, *_ = stats
            self.node.get_logger().info(f"[HzMonitor] {self.topic_name} Rate={rate:.2f}Hz")

    def run(self):
        while not self._stop_event.is_set():
            rclpy.spin_once(self.node, timeout_sec=0.1)

    def stop_monitor(self):
        self._stop_event.set()
        self.hz_monitor.stop_monitoring()

    def start_monitor(self):
        self._stop_event.clear()
        self.hz_monitor.start_monitoring(self.msg_type, self.qos_profile)

    def kill_monitor(self):
        self.stop_monitor()
        self.node.destroy_node()

    def get_node(self):
        return self.node
