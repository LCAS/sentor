#!/usr/bin/env python3
"""
Created on Thu Nov 21 10:30:22 2019

@author: Adam Binch (abinch@sagarobotics.com)
Modified for ROS2
"""
#####################################################################################
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.action import ActionClient
from rclpy.parameter import Parameter
from rcl_interfaces.msg import ParameterType
from rclpy.task import Future
import subprocess
import os
import numpy
import math
from threading import Lock
import importlib
from typing import Any, Dict, List, Optional, Tuple, Union
import time

def _import(location: str, name: str) -> Any:
    """Import a module dynamically"""
    mod = importlib.import_module(location)
    return getattr(mod, name)

class Executor:
    def __init__(self, config: List[Dict], event_cb: callable):
        """
        Initialize the executor
        
        Args:
            config: List of process configurations
            event_cb: Callback for reporting events
        """
        self.config = config
        self.event_cb = event_cb
        
        self.init_err_str = "Unable to initialise process of type '{}': {}"
        self._lock = Lock()
        self.processes = []
        
        # Create ROS2 node for the executor
        self.node = rclpy.create_node('sentor_executor')
        self.callback_group = ReentrantCallbackGroup()
        
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
            elif process_type == "parameter":  # renamed from reconf
                self.init_parameter(process)
            elif process_type == "lock_acquire":
                self.init_lock_acquire(process)
            elif process_type == "lock_release":
                self.init_lock_release(process)
            elif process_type == "custom":
                self.init_custom(process)
            else:
                self.event_cb(f"Process of type '{process_type}' not supported", "warn")
                self.processes.append("not_initialised")
        
        self.default_indices = range(len(self.processes))

    def init_call(self, process: Dict) -> None:
        """Initialize a service call process"""
        try:
            service_name = process["call"]["service_name"]
            service_name = self.get_name(service_name)
            
            # Import service type
            service_parts = process["call"]["service_type"].split('/')
            service_module = '.'.join(service_parts[:-1]) + '.srv'
            service_name_type = service_parts[-1]
            service_type = getattr(importlib.import_module(service_module), service_name_type)
            
            timeout_srv = process["call"].get("timeout", 1.0)
            
            # Create request
            req = service_type.Request()
            for arg in process["call"]["service_args"]:
                exec(arg)

            d = {
                "name": "call",
                "verbose": self.is_verbose(process["call"]),
                "def_msg": (f"Calling service '{service_name}'", "info", req),
                "func": "self.call(**kwargs)",
                "kwargs": {
                    "service_name": service_name,
                    "service_type": service_type,
                    "req": req,
                    "verbose": self.is_verbose(process["call"]),
                    "timeout_srv": timeout_srv
                }
            }
            self.processes.append(d)
            
        except Exception as e:
            self.event_cb(self.init_err_str.format("call", str(e)), "warn")
            self.processes.append("not_initialised")
            
    def call(self, service_name: str, service_type: Any, req: Any, verbose: bool, timeout_srv: float) -> None:
        """Execute a service call"""
        client = self.node.create_client(service_type, service_name)
        if not client.wait_for_service(timeout_sec=timeout_srv):
            self.event_cb(f"Service {service_name} not available", "warn")
            return
            
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        
        if future.result() is not None:
            response = future.result()
            if hasattr(response, 'success'):
                if verbose and response.success:
                    self.event_cb(f"Call to service '{service_name}' succeeded", "info", req)
                elif not response.success:
                    self.event_cb(f"Call to service '{service_name}' failed", "warn", req)
        else:
            self.event_cb(f"Service call to {service_name} failed", "warn")

    def publish(self, pub: Any, msg: Any) -> None:
        """Publish a message"""
        pub.publish(msg)

    async def action(self, namespace: str, spec: str, action_client: ActionClient, 
                    goal: Any, verbose: bool, wait: bool) -> None:
        """Send an action goal"""
        self.action_namespace = namespace
        self.spec = spec
        self.goal = goal
        self.verbose_action = verbose
        
        send_goal_future = action_client.send_goal_async(goal, feedback_callback=self.feedback_callback)
        rclpy.spin_until_future_complete(self.node, send_goal_future)
        
        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.event_cb(f"Goal rejected for '{namespace}' action", "warn", goal)
            return

        if wait:
            get_result_future = goal_handle.get_result_async()
            rclpy.spin_until_future_complete(self.node, get_result_future)
            
            result = get_result_future.result()
            if result.status == 4:  # SUCCEEDED
                if verbose:
                    self.event_cb(f"Goal succeeded for '{namespace}' action", "info", goal)
            else:
                self.event_cb(f"Goal failed for '{namespace}' action. Status is {result.status}", "warn", goal)

    def feedback_callback(self, feedback_msg: Any) -> None:
        """Handle action feedback"""
        if self.verbose_action:
            self.event_cb(f"Received feedback for '{self.action_namespace}' action", "info", feedback_msg.feedback)

    def sleep(self, duration: float) -> None:
        """Sleep for specified duration"""
        time.sleep(duration)

    def shell(self, cmd_args: List[str], shell_features: bool) -> None:
        """Execute shell commands"""
        process = subprocess.Popen(cmd_args,
                                 shell=shell_features,
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
                     
        stdout, stderr = process.communicate()
        print(stdout.decode())
        
        if stderr:
            self.event_cb(f"Unable to execute shell commands {cmd_args}: {stderr.decode()}", "warn")

    def log(self, message: str, level: str, msg_args: Optional[List[str]] = None) -> None:
        """Log a message"""
        msg = self.msg
        if msg is not None and msg_args is not None:
            args = [eval(arg) for arg in msg_args]
            self.event_cb("CUSTOM MSG: " + message.format(*args), level)
        else:
            self.event_cb("CUSTOM MSG: " + message, level)

    def parameter(self, params: List[Dict], default_params: List[Any]) -> None:
        """Update parameters"""
        for param, default_param in zip(params, default_params):
            node_name = param.get("node", "")  # Get target node name if specified
            if node_name:
                # Create a client to set parameters on another node
                from rclpy.parameter_client import ParameterClient
                client = ParameterClient(node=self.node, node_name=node_name)
                
                value = param["value"] if param["value"] != "_default" else default_param
                client.set_parameters([Parameter(param["name"], value=value)])
            else:
                # Set parameter on this node
                value = param["value"] if param["value"] != "_default" else default_param
                self.node.set_parameters([Parameter(param["name"], value=value)])

    def lock_acquire(self) -> None:
        """Acquire the lock"""
        self._lock.acquire()

    def lock_release(self) -> None:
        """Release the lock"""
        self._lock.release()

    def custom(self, cp: Any, args: Optional[List[Any]]) -> None:
        """Execute a custom process"""
        if args is not None:
            cp.run(*args)
        else:
            cp.run()

    def get_name(self, name: str) -> str:
        """Get name from environment or parameter server"""
        env_name = os.environ.get(name)
        if env_name is not None:
            return env_name
            
        try:
            return self.node.get_parameter(name).value
        except:
            return name

    def is_verbose(self, process: Dict) -> bool:
        """Check if process is verbose"""
        return process.get("verbose", False)

    def execute(self, msg: Any = None, process_indices: Optional[List[int]] = None) -> None:
        """Execute the configured processes"""
        self.msg = msg
        
        indices = process_indices if process_indices is not None else self.default_indices
        
        for index in indices:
            time.sleep(0.1)  # needed when using slackeros
            
            process = self.processes[index]
            if process == "not_initialised":
                continue
            
            try:
                if process["verbose"] and "def_msg" in process:
                    self.event_cb(process["def_msg"][0], process["def_msg"][1], process["def_msg"][2])
                    
                kwargs = process["kwargs"]            
                eval(process["func"])
                
            except Exception as e:
                self.event_cb(f"Unable to execute process of type '{process['name']}': {str(e)}", "warn")

    def cleanup(self) -> None:
        """Cleanup node"""
        self.node.destroy_node()
#####################################################################################