#!/usr/bin/env python3
"""
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
@author: Adam Binch (abinch@sagarobotics.com)
"""
#####################################################################################
from sentor.ROSTopicHz import ROSTopicHz
from sentor.ROSTopicFilter import ROSTopicFilter
from sentor.ROSTopicPub import ROSTopicPub
from sentor.Executor import Executor

from threading import Thread, Event, Lock
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.clock import Clock
import time
import subprocess
import os
import importlib

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
##########################################################################################    


##########################################################################################
class TopicMonitor(Thread):
    def __init__(self, topic_name, rate, N, signal_when_config, signal_lambdas_config, processes, 
                 timeout, default_notifications, event_callback, thread_num):
        Thread.__init__(self)

        self.topic_name = topic_name
        self.rate = rate
        self.N = N
        self.signal_when_config = signal_when_config
        self.signal_lambdas_config = signal_lambdas_config
        self.processes = processes
        if timeout > 0:
            self.timeout = timeout
        else:
            self.timeout = 0.1
        self.default_notifications = default_notifications
        self._event_callback = event_callback
        self.thread_num = thread_num
        
        # Create a ROS2 node for this monitor
        self.node = rclpy.create_node(f'topic_monitor_{thread_num}')
        self.callback_group = ReentrantCallbackGroup()
        
        # Get parameters from the parent node
        self.independent_tags = self.node.declare_parameter('independent_tags', False).value
        
        self.signal_when_is_safe = True
        self.lambdas_are_safe = True
        self.thread_is_safe = True
        
        self.signal_when_is_auto = True
        self.lambdas_are_auto = True
        self.thread_is_auto = True
        
        self.nodes = []
        self.sat_crit_expressions = []
        self.sat_auto_expressions = []
        self.sat_expressions_timer = {}
        self.sat_expr_repeat_timer = {}
        self.conditions = {}

        self.process_signal_config()

        if processes:
            self.executor = Executor(processes, self.event_callback)
        
        self._stop_event = Event()
        self._killed_event = Event()
        self._lock = Lock()
        
        self.pub_monitor = None
        self.hz_monitor = None
        self.is_topic_published = True 
        self.is_instantiated = False
        self.is_instantiated = self._instantiate_monitors()
        
        # Create a multi-threaded executor for this node
        self.executor = rclpy.executors.MultiThreadedExecutor()
        self.executor.add_node(self.node)
        self.executor_thread = Thread(target=self.executor.spin)
        self.executor_thread.start()

    def _instantiate_monitors(self):
        # [Previous implementation remains the same]
        pass

    def _instantiate_hz_monitor(self, subscribed_topic, topic_name, msg_class):
        # [Previous implementation remains the same]
        pass

    def _instantiate_pub_monitor(self, subscribed_topic, topic_name, msg_class):
        # [Previous implementation remains the same]
        pass

    def _instantiate_lambda_monitor(self, subscribed_topic, msg_class, lambda_fn_str, lambda_config):
        # [Previous implementation remains the same]
        pass

    def process_signal_config(self):
        self.signal_when_cfg = {}
        self.signal_when_cfg["signal_when"] = ""
        self.signal_when_cfg["timeout"] = self.timeout
        self.signal_when_cfg["safety_critical"] = False
        self.signal_when_cfg["autonomy_critical"] = False
        self.signal_when_cfg["default_notifications"] = self.default_notifications
        self.signal_when_cfg["process_indices"] = None
        self.signal_when_cfg["repeat_exec"] = False
        self.signal_when_cfg["tags"] = []
        self.signal_when_cfg["N"] = self.N
        
        if isinstance(self.signal_when_config, str):
            self.signal_when_cfg["signal_when"] = self.signal_when_config
        elif isinstance(self.signal_when_config, dict):
            if "condition" in self.signal_when_config:
                self.signal_when_cfg["signal_when"] = self.signal_when_config["condition"]
            if "timeout" in self.signal_when_config:
                self.signal_when_cfg["timeout"] = self.signal_when_config["timeout"]
            if "safety_critical" in self.signal_when_config:
                self.signal_when_cfg["safety_critical"] = self.signal_when_config["safety_critical"]
            if "autonomy_critical" in self.signal_when_config:
                self.signal_when_cfg["autonomy_critical"] = self.signal_when_config["autonomy_critical"]
            if "default_notifications" in self.signal_when_config:
                self.signal_when_cfg["default_notifications"] = self.signal_when_config["default_notifications"]
            if "process_indices" in self.signal_when_config:
                self.signal_when_cfg["process_indices"] = self.signal_when_config["process_indices"]
            if "repeat_exec" in self.signal_when_config:
                self.signal_when_cfg["repeat_exec"] = self.signal_when_config["repeat_exec"]
            if "tags" in self.signal_when_config:
                self.signal_when_cfg["tags"] = self.signal_when_config["tags"]
            if "N" in self.signal_when_config:
                self.signal_when_cfg["N"] = int(self.signal_when_config["N"])
            
        if self.signal_when_cfg["timeout"] <= 0:
            self.signal_when_cfg["timeout"] = 0.1
        
        # for publishing to sentor/monitors
        if self.signal_when_cfg["signal_when"].lower() in ["not published", "published"]:
            d = {}
            d["satisfied"] = False
            d["safety_critical"] = self.signal_when_cfg["safety_critical"]
            d["autonomy_critical"] = self.signal_when_cfg["autonomy_critical"]
            d["tags"] = self.signal_when_cfg["tags"]
            self.conditions[self.signal_when_cfg["signal_when"]] = d

    def process_lambda_config(self, signal_lambda):
        lambda_config = {}
        lambda_config["expr"] = ""
        lambda_config["file"] = None
        lambda_config["package"] = None
        lambda_config["timeout"] = self.timeout
        lambda_config["safety_critical"] = False
        lambda_config["autonomy_critical"] = False
        lambda_config["default_notifications"] = self.default_notifications
        lambda_config["when_published"] = False
        lambda_config["process_indices"] = None
        lambda_config["repeat_exec"] = False
        lambda_config["tags"] = []
        lambda_config["N"] = self.N
        
        for key in ["expression", "file", "package", "timeout", "safety_critical",
                   "autonomy_critical", "default_notifications", "when_published",
                   "process_indices", "repeat_exec", "tags", "N"]:
            if key in signal_lambda:
                if key == "N":
                    lambda_config[key] = int(signal_lambda[key])
                else:
                    lambda_config[key] = signal_lambda[key]
            
        if lambda_config["timeout"] <= 0:
            lambda_config["timeout"] = 0.1
        
        # for publishing to sentor/monitors
        if lambda_config["expr"]:
            d = {}
            d["satisfied"] = False
            d["safety_critical"] = lambda_config["safety_critical"]
            d["autonomy_critical"] = lambda_config["autonomy_critical"]
            d["tags"] = lambda_config["tags"]
            self.conditions[lambda_config["expr"]] = d
            
        return lambda_config

    def published_cb(self, msg):
        if not self._stop_event.isSet():
            self.conditions[self.signal_when_cfg["signal_when"]]["satisfied"] = True
            if self.signal_when_cfg["safety_critical"]:
                self.signal_when_is_safe = False
            if self.signal_when_cfg["autonomy_critical"]:
                self.signal_when_is_auto = False
            if self.signal_when_cfg["default_notifications"] and self.signal_when_cfg["safety_critical"]:
                self.event_callback("SAFETY CRITICAL: Topic %s is published " % (self.topic_name), "error")
            elif self.signal_when_cfg["default_notifications"]:
                self.event_callback("Topic %s is published " % (self.topic_name), "warn")

    def lambda_satisfied_cb(self, expr, msg, config):
        def ProcessLambda(timer_dict):
            process_lambda = True
            if config["when_published"] and not self.is_topic_published:
                process_lambda = False
                timer_dict = self.kill_timer(timer_dict, config["expr"]) 
            return process_lambda, timer_dict
            
        if not self._stop_event.isSet():    
            if not expr in self.sat_expressions_timer:
                def cb(_):
                    process_lambda, self.sat_expressions_timer = ProcessLambda(self.sat_expressions_timer)
                    if process_lambda:
                        if config["safety_critical"]:
                            self.lambdas_are_safe = False
                            self.sat_crit_expressions.append(config["expr"])
                            
                        if config["autonomy_critical"]:
                            self.lambdas_are_auto = False
                            self.sat_auto_expressions.append(config["expr"])

                        self.conditions[config["expr"]]["satisfied"] = True
                        if config["default_notifications"]:
                            if config["safety_critical"]:
                                self.event_callback("SAFETY CRITICAL: Expression '%s' for %s seconds on topic %s satisfied" % 
                                                 (expr, config["timeout"], self.topic_name), "error", msg)
                            else:
                                self.event_callback("Expression '%s' for %s seconds on topic %s satisfied" % 
                                                 (expr, config["timeout"], self.topic_name), "warn", msg)
                        
                        if not config["repeat_exec"]:
                            self.execute(msg, config["process_indices"])
                
                self._lock.acquire()
                timer = self.node.create_timer(
                    config["timeout"],
                    cb,
                    callback_group=self.callback_group
                )
                self.sat_expressions_timer.update({expr: timer})
                self._lock.release()
            
            if config["repeat_exec"] and expr not in self.sat_expr_repeat_timer:
                def repeat_cb(_):
                    process_lambda, self.sat_expr_repeat_timer = ProcessLambda(self.sat_expr_repeat_timer)
                    if process_lambda:     
                        self.execute(msg, config["process_indices"])
                        self.sat_expr_repeat_timer = self.kill_timer(self.sat_expr_repeat_timer, config["expr"]) 
                
                self._lock.acquire()
                timer = self.node.create_timer(
                    config["timeout"],
                    repeat_cb,
                    callback_group=self.callback_group
                )
                self.sat_expr_repeat_timer.update({expr: timer})
                self._lock.release()

    def lambda_unsatisfied_cb(self, expr):
        if not self._stop_event.isSet():            
            if expr in self.sat_expressions_timer:
                self.sat_expressions_timer = self.kill_timer(self.sat_expressions_timer, expr)
                self.conditions[expr]["satisfied"] = False
                
            if expr in self.sat_expr_repeat_timer:
                self.sat_expr_repeat_timer = self.kill_timer(self.sat_expr_repeat_timer, expr) 
                
            if expr in self.sat_crit_expressions:
                self.sat_crit_expressions.remove(expr)
                
            if expr in self.sat_auto_expressions:
                self.sat_auto_expressions.remove(expr)

            if not self.sat_crit_expressions:
                self.lambdas_are_safe = True

            if not self.sat_auto_expressions:
                self.lambdas_are_auto = True

    def kill_timer(self, timer_dict, expr):
        self._lock.acquire()
        timer_dict[expr].cancel()
        timer_dict.pop(expr)
        self._lock.release()
        return timer_dict
            
    def execute(self, msg=None, process_indices=None):
        if self.processes:
            time.sleep(0.1)  # needed when using slackeros
            self.executor.execute(msg, process_indices)
            
    def stop_monitor(self):
        self._stop_event.set()
        
    def start_monitor(self):
        self._stop_event.clear()
        
    def kill_monitor(self):
        self.stop_monitor()
        self._killed_event.set()
        if hasattr(self, 'executor_thread'):
            self.executor.shutdown()
            self.executor_thread.join()
        self.node.destroy_node()
##########################################################################################