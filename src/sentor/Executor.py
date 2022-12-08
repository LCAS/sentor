#!/usr/bin/env python
"""
Created on Thu Nov 21 10:30:22 2019

@author: Adam Binch (abinch@sagarobotics.com)
"""
#####################################################################################
import rospy, rosservice, rostopic, actionlib, subprocess
import dynamic_reconfigure.client
import os, numpy, math
from threading import Lock


def _import(location, name):
    mod = __import__(location, fromlist=[name]) 
    return getattr(mod, name) 


class Executor(object):
    
    
    def __init__(self, config, event_cb):

        self.config = config
        self.event_cb = event_cb
        
        self.init_err_str = "Unable to initialise process of type '{}': {}"
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
                self.event_cb("Process of type '{}' not supported".format(process_type), "warn")
                self.processes.append("not_initialised")
        
        self.default_indices = range(len(self.processes))        
                    
                    
    def init_call(self, process):
        
        try:
            service_name = process["call"]["service_name"]
            service_name = self.get_name(service_name)
                    
            service_class = rosservice.get_service_class_by_name(service_name)
            
            timeout_srv = 1.0
            if "timeout" in process["call"]:
                timeout_srv = process["call"]["timeout"]
            
            req = service_class._request_class()
            for arg in process["call"]["service_args"]: exec(arg)

            d = {}
            d["name"] = "call"
            d["verbose"] = self.is_verbose(process["call"])
            d["def_msg"] = ("Calling service '{}'".format(service_name), "info", req)
            d["func"] = "self.call(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["service_name"] = service_name
            d["kwargs"]["service_class"] = service_class
            d["kwargs"]["req"] = req
            d["kwargs"]["verbose"] = self.is_verbose(process["call"])
            d["kwargs"]["timeout_srv"] = timeout_srv
            
            self.processes.append(d)
            
        except Exception as e:
            self.event_cb(self.init_err_str.format("call", str(e)), "warn")
            self.processes.append("not_initialised")
            
            
    def init_publish(self, process):
        
        try:
            topic_name = process["publish"]["topic_name"]
            topic_name = self.get_name(topic_name)
            
            topic_latched = False
            if "topic_latched" in process["publish"]:
                topic_latched = process["publish"]["topic_latched"]
            
            msg_class, real_topic, _ = rostopic.get_topic_class(topic_name)
            pub = rospy.Publisher(real_topic, msg_class, latch=topic_latched, 
                                  queue_size=10)
            
            msg = msg_class()
            for arg in process["publish"]["topic_args"]: exec(arg)
                
            d = {}
            d["name"] = "publish"
            d["verbose"] = self.is_verbose(process["publish"])
            d["def_msg"] = ("Publishing to topic '{}'".format(topic_name), "info", msg)
            d["func"] = "self.publish(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["pub"] = pub
            d["kwargs"]["msg"] = msg
            
            self.processes.append(d)
            
        except Exception as e:
            self.event_cb(self.init_err_str.format("publish", str(e)), "warn")
            self.processes.append("not_initialised")
            
            
    def init_action(self, process):
        
        try:
            namespace = process["action"]["namespace"]
            package = process["action"]["package"]
            spec = process["action"]["action_spec"]
            
            action_spec = _import(package+".msg", spec)
            goal_class = _import(package+".msg", spec[:-6] + "Goal")

            rospy.sleep(1.0)
            
            action_client = actionlib.SimpleActionClient(namespace, action_spec)
            wait = action_client.wait_for_server(rospy.Duration(5.0))
            if not wait:
                e = "Action server with namespace '{}' and action specification '{}' not available".format(namespace, spec)
                self.event_cb(self.init_err_str.format("action", e), "warn")
                self.processes.append("not_initialised")
                return
    
            goal = goal_class()
            for arg in process["action"]["goal_args"]: exec(arg)
                
            d = {}
            d["name"] = "action"
            d["verbose"] = self.is_verbose(process["action"])
            d["def_msg"] = ("Sending goal for '{}' action with specification '{}'".format(namespace, spec), "info", goal)
            d["func"] = "self.action(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["namespace"] = namespace
            d["kwargs"]["spec"] = spec
            d["kwargs"]["action_client"] = action_client
            d["kwargs"]["goal"] = goal
            d["kwargs"]["verbose"] = self.is_verbose(process["action"])

            d["kwargs"]["wait"] = False            
            if "wait" in process["action"]:
                d["kwargs"]["wait"] = process["action"]["wait"]
            
            self.processes.append(d)
        
        except Exception as e:
            self.event_cb(self.init_err_str.format("action", str(e)), "warn")
            self.processes.append("not_initialised")
            
        
    def init_sleep(self, process):
        
        try:
            d = {}
            d["name"] = "sleep"
            d["verbose"] = self.is_verbose(process["sleep"])
            d["def_msg"] = ("Sentor sleeping for {} seconds".format(process["sleep"]["duration"]), "info", "")
            d["func"] = "self.sleep(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["duration"] = process["sleep"]["duration"]
            
            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("sleep", str(e)), "warn")
            self.processes.append("not_initialised")            
            
            
    def init_shell(self, process):
        
        try:
            d = {}
            d["name"] = "shell"
            d["verbose"] = self.is_verbose(process["shell"])
            d["def_msg"] = ("Executing shell commands {}".format(process["shell"]["cmd_args"]), "info", "")
            d["func"] = "self.shell(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["cmd_args"] = process["shell"]["cmd_args"]
            d["kwargs"]["shell_features"] = process["shell"]["shell_features"] if "shell_features" in process["shell"] else False
            
            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("shell", str(e)), "warn")
            self.processes.append("not_initialised")


    def init_log(self, process):
        
        try:            
            d = {}
            d["name"] = "log"
            d["verbose"] = False
            d["func"] = "self.log(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["message"] = process["log"]["message"]
            d["kwargs"]["level"] = process["log"]["level"]
            
            if "msg_args" in process["log"]:
                d["kwargs"]["msg_args"] = process["log"]["msg_args"]
            else:
                d["kwargs"]["msg_args"] = None                
            
            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("log", str(e)), "warn")
            self.processes.append("not_initialised")
            
            
    def init_reconf(self, process):
        
        try:
            params = process["reconf"]["params"]
            namespaces = set([param["namespace"] for param in params])
            
            default_config = {}
            for namespace in namespaces:
                rcnfclient = dynamic_reconfigure.client.Client(namespace, timeout=2.0)
                default_config[namespace] = rcnfclient.get_configuration()
                
            default_params = [default_config[param["namespace"]][param["name"]] for param in params]
            
            d = {}
            d["name"] = "reconf"
            d["verbose"] = self.is_verbose(process["reconf"])
            d["def_msg"] = ("Reconfiguring parameters: {}".format(params), "info", "")
            d["func"] = "self.reconf(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["params"] = params
            d["kwargs"]["default_params"] = default_params
            
            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("reconf", str(e)), "warn")
            self.processes.append("not_initialised")


    def init_lock_acquire(self, process):
        
        try:
            d = {}
            d["name"] = "lock_acquire"
            d["verbose"] = False
            d["func"] = "self.lock_acquire()"
            d["kwargs"] = {}
            
            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("lock_acquire", str(e)), "warn")
            self.processes.append("not_initialised")
            

    def init_lock_release(self, process):
        
        try:
            d = {}
            d["name"] = "lock_release"
            d["verbose"] = False
            d["func"] = "self.lock_release()"
            d["kwargs"] = {}
            
            self.processes.append(d)

        except Exception as e:
            self.event_cb(self.init_err_str.format("lock_release", str(e)), "warn")
            self.processes.append("not_initialised")
            
            
    def init_custom(self, process):
        
        try:
            package = process["custom"]["package"]
            name = process["custom"]["name"]
            
            _file = name
            if "file" in process["custom"]:
                _file = process["custom"]["file"]
            
            custom_proc = _import("{}.{}".format(package, _file), name)
            
            if "init_args" in process["custom"]:
                args = process["custom"]["init_args"] 
                cp = custom_proc(*args)
            else:
                cp = custom_proc()
            
            d = {}
            d["name"] = "custom"
            d["verbose"] = self.is_verbose(process["custom"])
            d["def_msg"] = ("Executing custom process '{}' from package '{}'".format(name, package), "info", "")
            d["func"] = "self.custom(**kwargs)"
            d["kwargs"] = {}
            d["kwargs"]["cp"] = cp
            
            d["kwargs"]["args"] = None
            if "run_args" in process["custom"]:
                d["kwargs"]["args"] = process["custom"]["run_args"]
            
            self.processes.append(d)
            
        except Exception as e:
            self.event_cb(self.init_err_str.format("custom", str(e)), "warn")
            self.processes.append("not_initialised")

        
    def get_name(self, name):
        
        env_name = os.environ.get(name)
        if env_name is not None:
            name = env_name
            
        if rospy.has_param(name):
            name = rospy.get_param(name)
            
        return name

        
    def is_verbose(self, process):
        
        verbose = False
        if "verbose" in process:
            verbose = process["verbose"]
            
        return verbose
            
        
    def execute(self, msg=None, process_indices=None):
        
        self.msg = msg
        
        if process_indices is None:
            indices = self.default_indices
        else:
            indices = process_indices
        
        for index in indices:
            
            process = self.processes[index]
            if process == "not_initialised":
                continue
            
            try:
                if process["verbose"] and "def_msg" in process:
                    self.event_cb(process["def_msg"][0], process["def_msg"][1], process["def_msg"][2])
                    
                kwargs = process["kwargs"]            
                eval(process["func"])
                
            except Exception as e:
                self.event_cb("Unable to execute process of type '{}': {}".format(process["name"], str(e)), "warn")
            

    def call(self, service_name, service_class, req, verbose, timeout_srv):
        
        rospy.wait_for_service(service_name, timeout=timeout_srv)
        service_client = rospy.ServiceProxy(service_name, service_class)
        resp = service_client(req)
        
        if verbose and resp.success:
            self.event_cb("Call to service '{}' succeeded".format(service_name), "info", req)
        elif not resp.success:
            self.event_cb("Call to service '{}' failed".format(service_name), "warn", req)
        
        
    def publish(self, pub, msg):
        pub.publish(msg)
        
        
    def action(self, namespace, spec, action_client, goal, verbose, wait):
        
        self.action_namespace = namespace
        self.spec = spec
        self.goal = goal
        self.verbose_action = verbose
        
        action_client.send_goal(goal, self.goal_cb)
        
        if wait:
            action_client.wait_for_result()
            
        
    def sleep(self, duration):
        rospy.sleep(duration)
        
        
    def shell(self, cmd_args, shell_features):
        
        process = subprocess.Popen(cmd_args,
                     shell=shell_features,
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE)
                     
        stdout, stderr = process.communicate()
        print(stdout)
        
        if stderr:
            self.event_cb("Unable to execute shell commands {}: {}".format(cmd_args, stderr), "warn")
        
    
    def log(self, message, level, msg_args):
        
        msg = self.msg
        if msg is not None and msg_args is not None:
            args = []
            for arg in msg_args:
                args.append(eval(arg))
            self.event_cb("CUSTOM MSG: " + message.format(*args), level)
        else:
            self.event_cb("CUSTOM MSG: " + message, level)
            
            
    def reconf(self, params, default_params):
        
        for param, default_param in zip(params, default_params):            
            rcnfclient = dynamic_reconfigure.client.Client(param["namespace"], timeout=1.0)
            
            if param["value"] != "_default":
                value = param["value"]
            else:
                value = default_param
                
            rcnfclient.update_configuration({param["name"]: value})
            
            
    def lock_acquire(self):
        self._lock.acquire()


    def lock_release(self):
        self._lock.release()
        
        
    def custom(self, cp, args):
        cp.run(*args) if args is not None else cp.run()
         
        
    def goal_cb(self, status, result):
        
        if self.verbose_action and status == 3:
            self.event_cb("Goal succeeded for '{}' action with specification '{}'".format(self.action_namespace, self.spec), "info", self.goal)
        elif status == 2:
            self.event_cb("Goal preempted for '{}' action with specification '{}'".format(self.action_namespace, self.spec), "warn", self.goal)
        elif status != 3:
            self.event_cb("Goal failed for '{}' action with specification '{}'. Status is {}".format(self.action_namespace, self.spec, status), "warn", self.goal)
#####################################################################################