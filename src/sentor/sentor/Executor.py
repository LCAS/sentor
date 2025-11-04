#!/usr/bin/env python3
"""
Created on Thu Nov 21 10:30:22 2019
@author: Adam Binch (abinch@sagarobotics.com)

Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang

Description:
This script defines an Executor node in ROS2 that handles various tasks such as:
- Calling ROS2 services
- Publishing to topics
- Executing ROS2 actions
- Running shell commands
- Logging messages
- Dynamically reconfiguring parameters
- Managing thread locks
"""
#####################################################################################
# Import necessary ROS2 libraries
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.publisher import Publisher
from rclpy.subscription import Subscription
from rclpy.service import Service
from rclpy.parameter import Parameter
from rcl_interfaces.msg import SetParametersResult

# Import standard Python libraries
import os
import numpy as np
import importlib
import math
import time
from threading import Lock
import subprocess

# Import function for getting ROS2 service types dynamically
from sentor.service_types import get_service_type 

def _import(location, name):
    """
    Dynamically imports a module and returns the specified attribute.

    Args:
    - location (str): The module's location.
    - name (str): The attribute to fetch from the module.

    Returns:
    - The imported attribute.
    """
    mod = __import__(location, fromlist=[name]) 
    return getattr(mod, name)

class Executor(Node):
    """
    Executor node that manages different types of processes in ROS2.
    """
    def __init__(self, config, event_cb):
        """
        Initializes the Executor node.

        Args:
        - config (list): List of process configurations.
        - event_cb (function): Callback function for event logging.
        """
        super().__init__('executor_node')
        self.config = config
        self.event_cb = event_cb
        self.topic_type_cache: dict[str, type] = {} # NEW: cache to avoid repeating expensive look‑ups

        self.init_err_str = "Unable to initialize process of type '{}': {}"
        self._lock = Lock()
        self.processes = []
        
        for process in config:
            process_type = list(process.keys())[0]
            
            if process_type == "call":
                self.init_call(process)
            elif process_type == "publish":
                self.init_publish(process)
            elif process_type == "action":
                self.init_action(process)
            elif process_type == "sleep":
                self.init_sleep(process)
            elif process_type == "shell":
                self.init_shell(process)
            elif process_type == "log":
                self.init_log(process)
            elif process_type == "reconf":
                self.init_reconf(process)
            elif process_type == "lock_acquire":
                self.init_lock_acquire(process)
            elif process_type == "lock_release":
                self.init_lock_release(process)
            elif process_type == "custom":
                self.init_custom(process)
            else:
                self.event_cb(f"Process of type '{process_type}' not supported", "warn")
                self.processes.append("not_initialized")

        self.default_indices = range(len(self.processes))

    def init_call(self, process):
        """
        Initializes a ROS2 action client.
        """
        try:
            service_name = process["call"]["service_name"]
            service_name = self.get_param_name(service_name)

            # FIX: Get the service type manually
            service_class = get_service_type(service_name)

            timeout_srv = process["call"].get("timeout", 1.0)

            req = service_class.Request()  # FIX: Correct way to create a service request in ROS2
            for arg in process["call"]["service_args"]:
                exec(arg)

            d = {
                "name": "call",
                "verbose": self.is_verbose(process["call"]),
                "def_msg": (f"Calling service '{service_name}'", "info", req),
                "func": "self.call(**kwargs)",
                "kwargs": {
                    "service_name": service_name,
                    "service_class": service_class,
                    "req": req,
                    "verbose": self.is_verbose(process["call"]),
                    "timeout_srv": timeout_srv,
                }
            }

            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("call", str(e)), "warn")
            self.processes.append("not_initialized")
        
    def get_topic_msg_class(self, topic_name):
        """Return the *message class* for *topic_name* using rclpy APIs.

        Caches lookups to avoid repeated expensive graph traversals.
        """
        # 1. Cached already? --------------------------------------------------
        if topic_name in self.topic_type_cache:
            return self.topic_type_cache[topic_name]

        # 2. Query the ROS 2 graph -------------------------------------------
        topic_names_and_types = self.get_topic_names_and_types()
        for name, types in topic_names_and_types:
            if name == topic_name and types:
                ros2_type = types[0]  # e.g. "std_msgs/msg/String"
                break
        else:
            raise ValueError(f"Unknown topic type for '{topic_name}'. Is it currently advertised?")

        # 3. Convert ROS2 type → Python import path ---------------------------
        # std_msgs/msg/String -> std_msgs.msg.String
        parts = ros2_type.split('/')  # [pkg, 'msg', MsgName]
        if len(parts) != 3 or parts[1] != 'msg':
            raise ValueError(f"Unexpected type string '{ros2_type}' for topic '{topic_name}'")

        module_name = f"{parts[0]}.msg"
        class_name = parts[2]

        try:
            module = importlib.import_module(module_name)
            msg_class = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot import message class for '{ros2_type}': {e}")

        # 4. Cache & return ----------------------------------------------------
        self.topic_type_cache[topic_name] = msg_class
        return msg_class

    def init_publish(self, process):
        try:
            topic_name = self.get_param_name(process["publish"]["topic_name"])
            msg_class = self.get_topic_msg_class(topic_name)

            pub = self.create_publisher(msg_class, topic_name, 10)

            msg = msg_class()
            for arg in process["publish"]["topic_args"]:
                exec(arg)

            self.processes.append({
                "name": "publish",
                "verbose": self.is_verbose(process["publish"]),
                "def_msg": (f"Publishing to topic '{topic_name}'", "info", msg),
                "func": "self.publish(**kwargs)",
                "kwargs": {"pub": pub, "msg": msg},
            })
        except Exception as e:
            self.event_cb(self.init_err_str.format("publish", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_action(self, process):
        try:
            namespace = process["action"]["namespace"]
            package = process["action"]["package"]
            spec = process["action"]["action_spec"]

            action_spec = _import(package+".action", spec)
            goal_class = _import(package+".action", spec[:-6] + "Goal")

            action_client = ActionClient(self, action_spec, namespace)
            goal = goal_class()
            for arg in process["action"]["goal_args"]:
                exec(arg)

            d = {
                "name": "action",
                "verbose": self.is_verbose(process["action"]),
                "def_msg": (f"Sending goal for '{namespace}' action with spec '{spec}'", "info", goal),
                "func": "self.action(**kwargs)",
                "kwargs": {
                    "namespace": namespace,
                    "spec": spec,
                    "action_client": action_client,
                    "goal": goal,
                    "verbose": self.is_verbose(process["action"]),
                    "wait": process["action"].get("wait", False),
                }
            }

            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("action", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_reconf(self, process):
        try:
            params = process["reconf"]["params"]
            namespaces = set(param["namespace"] for param in params)

            for param in params:
                self.declare_parameter(f"{param['namespace']}.{param['name']}", param["value"])

            default_config = {
                namespace: self.get_parameters_by_prefix(namespace) for namespace in namespaces
            }

            default_params = [
                default_config[param["namespace"]][param["name"]].value for param in params
            ]

            d = {
                "name": "reconf",
                "verbose": self.is_verbose(process["reconf"]),
                "def_msg": (f"Reconfiguring parameters: {params}", "info", ""),
                "func": "self.reconf(**kwargs)",
                "kwargs": {"params": params, "default_params": default_params},
            }

            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("reconf", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_lock_acquire(self, process):
        """ Initializes a process that acquires a thread lock """
        try:
            d = {
                "name": "lock_acquire",
                "verbose": False,
                "func": "self.lock_acquire()",
                "kwargs": {}
            }
            self.processes.append(d)
        except Exception as e:
            self.event_cb(self.init_err_str.format("lock_acquire", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_lock_release(self, process):
        """ Initializes a process that releases a thread lock """
        try:
            d = {
                "name": "lock_release",
                "verbose": False,
                "func": "self.lock_release()",
                "kwargs": {}
            }
            self.processes.append(d)
        except Exception as e:
            self.event_cb(self.init_err_str.format("lock_release", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_custom(self, process):
        """ Initializes a custom process from a package and module """
        try:
            package = process["custom"]["package"]
            name = process["custom"]["name"]

            _file = process["custom"].get("file", name)
            custom_proc = _import(f"{package}.{_file}", name)

            cp = custom_proc(*process["custom"].get("init_args", []))

            d = {
                "name": "custom",
                "verbose": self.is_verbose(process["custom"]),
                "def_msg": (f"Executing custom process '{name}' from package '{package}'", "info", ""),
                "func": "self.custom(**kwargs)",
                "kwargs": {
                    "cp": cp,
                    "args": process["custom"].get("run_args", None)
                }
            }

            self.processes.append(d)
        except Exception as e:
            self.event_cb(self.init_err_str.format("custom", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_sleep(self, process):
        """ Initializes a process that will sleep for a given duration """
        try:
            d = {
                "name": "sleep",
                "verbose": self.is_verbose(process["sleep"]),
                "def_msg": (f"Sentor sleeping for {process['sleep']['duration']} seconds", "info", ""),
                "func": "self.sleep(**kwargs)",
                "kwargs": {
                    "duration": process["sleep"]["duration"]
                }
            }
            self.processes.append(d)
        except Exception as e:
            self.event_cb(self.init_err_str.format("sleep", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_shell(self, process):
        """ Initializes a process that will execute a shell command """
        try:
            d = {
                "name": "shell",
                "verbose": self.is_verbose(process["shell"]),
                "def_msg": (f"Executing shell command {process['shell']['cmd_args']}", "info", ""),
                "func": "self.shell(**kwargs)",
                "kwargs": {
                    "cmd_args": process["shell"]["cmd_args"],
                    "shell_features": process["shell"].get("shell_features", False)
                }
            }
            self.processes.append(d)
        except Exception as e:
            self.event_cb(self.init_err_str.format("shell", str(e)), "warn")
            self.processes.append("not_initialized")

    def init_log(self, process):
        """ Initializes a logging process """
        try:
            d = {
                "name": "log",
                "verbose": False,
                "func": "self.log(**kwargs)",
                "kwargs": {
                    "message": process["log"]["message"],
                    "level": process["log"]["level"],
                    "msg_args": process["log"].get("msg_args", None)
                }
            }
            self.processes.append(d)
        except Exception as e:
            self.event_cb(self.init_err_str.format("log", str(e)), "warn")
            self.processes.append("not_initialized")
    
    def execute(self, msg=None, process_indices=None):
        """
        Executes the configured processes.
        """
        self.msg = msg
        if process_indices is None:
            indices = self.default_indices
        else:
            indices = process_indices 

        for index in indices:
            process = self.processes[index]
            if process == "not_initialized":
                continue

            try:
                if process["verbose"] and "def_msg" in process:
                    self.event_cb(process["def_msg"][0], process["def_msg"][1], process["def_msg"][2])

                kwargs = process["kwargs"]
                eval(process["func"])

            except Exception as e:
                self.event_cb(f"Unable to execute process of type '{process['name']}': {str(e)}", "warn")

    def get_param_name(self, name):
        """ Retrieves a parameter's value, checking environment variables and ROS parameters """
        env_name = os.environ.get(name)
        if env_name is not None:
            return env_name

        if self.has_parameter(name):
            return self.get_parameter(name).value

        return name

    def is_verbose(self, process):
        """ Checks if verbosity is enabled for a process """
        return process.get("verbose", False)
    
    def sleep(self, duration):
        """ Sleeps for a given duration in seconds """
        self.get_logger().info(f"Sleeping for {duration} seconds...")
        time.sleep(duration)  # FIX: Replaced `rclpy.sleep()` with `time.sleep()`

    def call(self, service_name, service_class, req, verbose, timeout_srv):
        """ Calls a ROS2 service """
        self.get_logger().info(f"Waiting for service '{service_name}'...")
        client = self.create_client(service_class, service_name)
        
        if not client.wait_for_service(timeout_sec=timeout_srv):
            self.event_cb(f"Service '{service_name}' not available", "warn")
            return
        
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.done():
            response = future.result()
            if verbose and response:
                self.event_cb(f"Call to service '{service_name}' succeeded", "info", req)
            else:
                self.event_cb(f"Call to service '{service_name}' failed", "warn", req)
        else:
            self.event_cb(f"Call to service '{service_name}' did not complete", "warn")


    def publish(self, pub, msg):
        """ Publishes a message to a ROS2 topic """
        pub.publish(msg)

    def action(self, namespace, spec, action_client, goal, verbose, wait):
        """ Sends a goal to a ROS2 action server """
        self.action_namespace = namespace
        self.spec = spec
        self.goal = goal
        self.verbose_action = verbose

        future = action_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)

        if wait:
            result_future = future.result().get_result_async()
            rclpy.spin_until_future_complete(self, result_future)

    def shell(self, cmd_args, shell_features):
        """ Executes a shell command """
        process = subprocess.Popen(cmd_args,
                                   shell=shell_features,
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)

        stdout, stderr = process.communicate()
        print(stdout.decode())

        if stderr:
            self.event_cb(f"Unable to execute shell commands {cmd_args}: {stderr.decode()}", "warn")

    def log(self, message, level, msg_args):
        """ Logs a custom message """
        msg = self.msg
        if msg is not None and msg_args is not None:
            args = [eval(arg) for arg in msg_args]
            self.event_cb(f"CUSTOM MSG: {message.format(*args)}", level)
        else:
            self.event_cb(f"CUSTOM MSG: {message}", level)

    def reconf(self, params, default_params):
        """ Updates parameters dynamically in ROS2 """
        try:
            self.set_parameters([
                Parameter(f"{param['namespace']}.{param['name']}", Parameter.Type.DOUBLE, 
                          param["value"] if param["value"] != "_default" else default_param)
                for param, default_param in zip(params, default_params)
            ])
        except Exception as e:
            self.event_cb(f"Unable to reconfigure parameters: {str(e)}", "warn")

    def lock_acquire(self):
        """ Acquires a thread lock """
        self._lock.acquire()

    def lock_release(self):
        """ Releases a thread lock """
        self._lock.release()

    def custom(self, cp, args):
        """ Executes a custom process """
        cp.run(*args) if args is not None else cp.run()

    def goal_cb(self, status, result):
        """ Handles action goal completion """
        if self.verbose_action and status == 3:
            self.event_cb(f"Goal succeeded for '{self.action_namespace}' action with specification '{self.spec}'", "info", self.goal)
        elif status == 2:
            self.event_cb(f"Goal preempted for '{self.action_namespace}' action with specification '{self.spec}'", "warn", self.goal)
        elif status != 3:
            self.event_cb(f"Goal failed for '{self.action_namespace}' action with specification '{self.spec}'. Status is {status}", "warn", self.goal)


def main(args=None):
    rclpy.init(args=args)
    executor = Executor([], print)
    rclpy.spin(executor)
    executor.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
