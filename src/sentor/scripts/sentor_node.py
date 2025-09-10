#!/usr/bin/env python3
"""
Created on 20 May 2025

@author: Zhuoling Huang
"""
import os
import yaml
import signal

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from std_srvs.srv import Empty

from sentor.MultiMonitor   import MultiMonitor
from sentor.TopicMonitor   import TopicMonitor
from sentor.NodeMonitor    import NodeMonitor
from sentor.SafetyMonitor  import SafetyMonitor

# ─── Globals ────────────────────────────────────────────────────────────────
topic_monitors = []
node_monitors  = []
multi_monitor  = None

def shutdown_handler(signum, frame):
    for tm in topic_monitors:
        tm.stop_monitor()
    for nm in node_monitors:
        nm.stop_monitor()
    if multi_monitor:
        multi_monitor.stop_monitor()
    rclpy.shutdown()

signal.signal(signal.SIGINT, shutdown_handler)

# ─── Services ───────────────────────────────────────────────────────────────
def start_monitoring(request, _):
    for tm in topic_monitors: tm.start_monitor()
    for nm in node_monitors:  nm.start_monitor()
    multi_monitor.start_monitor()
    return Empty.Response()

def stop_monitoring(request, _):
    for tm in topic_monitors: tm.stop_monitor()
    for nm in node_monitors:  nm.stop_monitor()
    multi_monitor.stop_monitor()
    return Empty.Response()

def event_callback(msg, level="info", **_):
    print(f"[{level.upper()}] {msg}")

# ─── Helpers ────────────────────────────────────────────────────────────────
def get_message_type(type_str):
    pkg, msg = type_str.split('/msg/')
    module = __import__(f"{pkg}.msg", fromlist=[msg])
    return getattr(module, msg)

def get_qos_profile(qos):
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
    rel = ReliabilityPolicy.BEST_EFFORT if qos.get("reliability","").lower()=="best_effort" else ReliabilityPolicy.RELIABLE
    dur = DurabilityPolicy.TRANSIENT_LOCAL if qos.get("durability","").lower()=="transient_local" else DurabilityPolicy.VOLATILE
    hist= HistoryPolicy.KEEP_ALL if qos.get("history","").lower()=="keep_all" else HistoryPolicy.KEEP_LAST
    return QoSProfile(reliability=rel, durability=dur, history=hist, depth=qos.get("depth",10))

# ─── main() ─────────────────────────────────────────────────────────────────
def main():
    global topic_monitors, node_monitors, multi_monitor

    rclpy.init()
    driver = rclpy.create_node("test_sentor")

    # load config
    cfg_path = driver.declare_parameter("config_file","~/config/test_monitor_config.yaml")\
                     .get_parameter_value().string_value
    cfg_path = os.path.expanduser(cfg_path)
    with open(cfg_path,'r') as f:
        cfg = yaml.safe_load(f) or {}

    topics_cfg = cfg.get("monitors",   [])
    nodes_cfg  = cfg.get("node_monitors", [])

    # start/stop services
    driver.create_service(Empty, "start_monitoring", start_monitoring)
    driver.create_service(Empty, "stop_monitoring",  stop_monitoring)

    # multi_monitor
    multi_monitor = MultiMonitor()

    # 1) TopicMonitors
    for idx, t in enumerate(topics_cfg):
        # ensure every condition—and every lambda—has a tags list
        t.setdefault("signal_when", {}).setdefault("tags", [])
        for lam in t.get("signal_lambdas", []):
            lam.setdefault("tags", [])

        tm = TopicMonitor(
            topic_name            = t["name"],
            msg_type              = get_message_type(t["message_type"]),
            qos_profile           = get_qos_profile(t.get("qos",{})),
            rate                  = t["rate"],
            N                     = t["N"],
            signal_when_config    = t.get("signal_when", {}),
            signal_lambdas_config = t.get("signal_lambdas", []),
            processes             = t.get("execute", []),
            timeout               = t.get("timeout", 0.1),
            default_notifications = t.get("default_notifications", True),
            event_callback        = event_callback,
            thread_num            = idx,
            enable_internal_logs  = True,
        )
        topic_monitors.append(tm)
        multi_monitor.register_monitor(tm)

    # 2) NodeMonitors
    for n in nodes_cfg:
        nm = NodeMonitor(
            target_node_name  = n["name"],
            timeout           = n["timeout"],
            event_callback    = event_callback,
            safety_critical   = n.get("safety_critical", False),
            autonomy_critical = n.get("autonomy_critical", False),
            poll_rate         = n.get("poll_rate", 1.0),
        )
        node_monitors.append(nm)

    # 3) safety heartbeat (safety_critical)
    safety_hb = SafetyMonitor(
        topic     = 'safety/heartbeat',
        event_msg = 'Heartbeat',
        attr      = 'is_alive',
        srv_name  = 'heartbeat_override',
        event_cb  = event_callback,
        invert    = False,
    )
    # register both topic & node monitors
    for tm in topic_monitors:
        if tm.signal_when_cfg.get("safety_critical") or \
           any(l.get("safety_critical") for l in tm.signal_lambdas_config):
            safety_hb.register_monitor(tm)
    for nm in node_monitors:
        if nm.safety_critical:
            safety_hb.register_monitor(nm)

    # 4) warning heartbeat (autonomy_critical)
    warning_hb = SafetyMonitor(
        topic     = 'warning/heartbeat',
        event_msg = 'Warning-beat',
        attr      = 'is_autonomy_alive',
        srv_name  = 'warning_override',
        event_cb  = event_callback,
        invert    = False,
    )
    for tm in topic_monitors:
        if tm.signal_when_cfg.get("autonomy_critical") or \
           any(l.get("autonomy_critical") for l in tm.signal_lambdas_config):
            warning_hb.register_monitor(tm)
    for nm in node_monitors:
        if nm.autonomy_critical:
            warning_hb.register_monitor(nm)

    # 5) spin everything together
    executor = MultiThreadedExecutor()
    executor.add_node(driver)
    executor.add_node(multi_monitor)
    executor.add_node(safety_hb)
    executor.add_node(warning_hb)
    for tm in topic_monitors:
        executor.add_node(tm.get_node())
    for nm in node_monitors:
        executor.add_node(nm.node)

    executor.spin()
    rclpy.shutdown()

if __name__ == "__main__":
    main()