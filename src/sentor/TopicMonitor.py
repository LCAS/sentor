#!/usr/bin/env python
"""
@author: Adam Binch (abinch@sagarobotics.com)
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
"""
#####################################################################################
from sentor.ROSTopicHz import ROSTopicHz
from sentor.ROSTopicFilter import ROSTopicFilter
from sentor.ROSTopicPub import ROSTopicPub
from sentor.Executor import Executor

from threading import Thread, Event, Lock
import socket
import rostopic
import rosgraph
import rospy
import time
import subprocess
import os
import uuid

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
                 timeout, default_notifications, event_callback, topic_tags):
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
        self.topic_tags = topic_tags
        
        self.independent_tags = rospy.get_param("~independent_tags", False)
        
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
        self.active = False
        self.is_instantiated = self._instantiate_monitors()


    def _instantiate_monitors(self):
        if self.is_instantiated: return True

        real_topic = None
        _set = False
        while real_topic is None:
            
            try:
                msg_class, real_topic, _ = rostopic.get_topic_class(self.topic_name, blocking=False)
                topic_type, _, _ = rostopic.get_topic_type(self.topic_name, blocking=False)
            except rostopic.ROSTopicException as e:
                self.event_callback("Topic %s type cannot be determined, or ROS master cannot be contacted" % self.topic_name, "warn")
                real_topic = None
    
            if real_topic is None:
                if not _set:
                    self.set_not_published(_exec=False)
                    if self.signal_when_cfg["signal_when"].lower() == 'not published':
                        self.execute(process_indices=self.signal_when_cfg["process_indices"])
                    _set = True
                rospy.sleep(0.1)
            

        # if rate > 0 set in config then throttle topic at that rate
        if self.rate > 0:
            _id = "".join(str(uuid.uuid4()).split("-"))
            
            COMMAND_BASE = ["rosrun", "topic_tools", "throttle"]
            subscribed_topic = "/sentor/monitoring/" + _id + real_topic
            
            command = COMMAND_BASE + ["messages", real_topic, str(self.rate), subscribed_topic]
            subprocess.Popen(command, stdout=open(os.devnull, "wb"))
        else:
            subscribed_topic = real_topic

        # find out topic publishing nodes
        master = rosgraph.Master(rospy.get_name())
        try:
            pubs, _ = rostopic.get_topic_list(master=master)
            # filter based on topic
            pubs = [x for x in pubs if x[0] == real_topic]
            nodes = []
            for _, _, _nodes in pubs:
                nodes += _nodes
            self.nodes = nodes
        except socket.error:
            self.event_callback("Could not retrieve nodes for topic %s" % self.topic_name, "warn")

        # Do we need a hz monitor?
        hz_monitor_required = False
        if self.signal_when_cfg["signal_when"].lower() == 'not published':
            hz_monitor_required = True
        for signal_lambda in self.signal_lambdas_config:
             if "when_published" in signal_lambda:
                 if signal_lambda["when_published"]:
                     hz_monitor_required = True
        
        if hz_monitor_required:
            self.hz_monitor = self._instantiate_hz_monitor(subscribed_topic, self.topic_name, msg_class)

        if self.signal_when_cfg["signal_when"].lower() == 'published':
            print("Signaling 'published' for "+ bcolors.OKBLUE + self.topic_name + bcolors.ENDC +" initialized")
            self.pub_monitor = self._instantiate_pub_monitor(subscribed_topic, self.topic_name, msg_class)
            self.pub_monitor.register_published_cb(self.published_cb)
            
            if self.signal_when_cfg["safety_critical"]:
                self.signal_when_is_safe = False

        elif self.signal_when_cfg["signal_when"].lower() == 'not published':
            print("Signaling 'not published' for "+ bcolors.BOLD + str(self.signal_when_cfg["timeout"]) + " seconds" + bcolors.ENDC +" for " + bcolors.OKBLUE + self.topic_name + bcolors.ENDC +" initialized")

        if len(self.signal_lambdas_config):
            print("Signaling expressions for "+ bcolors.OKBLUE + self.topic_name + bcolors.ENDC + ":")
            
            self.lambda_monitor_list = []
            for signal_lambda in self.signal_lambdas_config:
                
                lambda_fn_str = signal_lambda["expression"]
                lambda_config = self.process_lambda_config(signal_lambda)
                
                if lambda_fn_str != "":
                    print("\t" + bcolors.OKGREEN + lambda_fn_str + bcolors.ENDC + " ("+ bcolors.BOLD+"timeout: %s seconds" %  lambda_config["timeout"] + bcolors.ENDC +")")
                    lambda_monitor = self._instantiate_lambda_monitor(subscribed_topic, msg_class, lambda_fn_str, lambda_config)

                    # register cb that notifies when the lambda function is True
                    lambda_monitor.register_satisfied_cb(self.lambda_satisfied_cb)
                    lambda_monitor.register_unsatisfied_cb(self.lambda_unsatisfied_cb)

                    self.lambda_monitor_list.append(lambda_monitor)
            print("")

        self.is_instantiated = True
        self.active = True

        return True
    

    def event_callback(self, string, type, msg=""):
        self._event_callback(string, type, msg, self.nodes, self.topic_name)
        
        
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
        
        if type(self.signal_when_config) is str:
            self.signal_when_cfg["signal_when"] = self.signal_when_config
        elif type(self.signal_when_config) is dict:
        
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
        if self.signal_when_cfg["signal_when"].lower() == "not published" \
        or self.signal_when_cfg["signal_when"].lower() == "published":
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
        lambda_config["init_args"] = None
        lambda_config["run_args"] = None
        lambda_config["timeout"] = self.timeout
        lambda_config["safety_critical"] = False
        lambda_config["autonomy_critical"] = False
        lambda_config["default_notifications"] = self.default_notifications
        lambda_config["when_published"] = False
        lambda_config["process_indices"] = None
        lambda_config["repeat_exec"] = False
        lambda_config["tags"] = []
        lambda_config["N"] = self.N
        
        if "expression" in signal_lambda:
            lambda_config["expr"] = signal_lambda["expression"]
        if "file" in signal_lambda:
            lambda_config["file"] = signal_lambda["file"]
        if "package" in signal_lambda:
            lambda_config["package"] = signal_lambda["package"]
        if "init_args" in signal_lambda:
            lambda_config["init_args"] = signal_lambda["init_args"]
        if "run_args" in signal_lambda:
            lambda_config["run_args"] = signal_lambda["run_args"]
        if "timeout" in signal_lambda:
            lambda_config["timeout"] = signal_lambda["timeout"]
        if "safety_critical" in signal_lambda:
            lambda_config["safety_critical"] = signal_lambda["safety_critical"]
        if "autonomy_critical" in signal_lambda:
            lambda_config["autonomy_critical"] = signal_lambda["autonomy_critical"]
        if "default_notifications" in signal_lambda:
            lambda_config["default_notifications"] = signal_lambda["default_notifications"]    
        if "when_published" in signal_lambda:
            lambda_config["when_published"] = signal_lambda["when_published"]
        if "process_indices" in signal_lambda:
            lambda_config["process_indices"] = signal_lambda["process_indices"]
        if "repeat_exec" in signal_lambda:
            lambda_config["repeat_exec"] = signal_lambda["repeat_exec"]      
        if "tags" in signal_lambda:
            lambda_config["tags"] = signal_lambda["tags"]      
        if "N" in signal_lambda:
            lambda_config["N"] = int(signal_lambda["N"])
            
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
        

    def _instantiate_hz_monitor(self, subscribed_topic, topic_name, msg_class):
        hz = ROSTopicHz(topic_name, 1000, self.signal_when_cfg["N"])
        
        if self.signal_when_cfg["N"] <= 0:
            cb = hz.callback_hz
        else:
            cb = hz.callback_hz_throttled

        rospy.Subscriber(subscribed_topic, msg_class, cb)

        return hz
        

    def _instantiate_pub_monitor(self, subscribed_topic, topic_name, msg_class):
        pub = ROSTopicPub(topic_name, self.signal_when_cfg["N"])
        
        if self.signal_when_cfg["N"] <= 0:
            cb = pub.callback_pub
        else:
            cb = pub.callback_pub_throttled

        rospy.Subscriber(subscribed_topic, msg_class, cb)

        return pub
        

    def _instantiate_lambda_monitor(self, subscribed_topic, msg_class, lambda_fn_str, lambda_config):
        _filter = ROSTopicFilter(self.topic_name, lambda_fn_str, lambda_config, lambda_config["N"])

        if lambda_config["N"] <= 0:
            cb = _filter.callback_filter
        else:
            cb = _filter.callback_filter_throttled
            
        rospy.Subscriber(subscribed_topic, msg_class, cb)

        return _filter
    
    
    def set_not_published(self, _exec=True):
        
        if self.signal_when_cfg["signal_when"].lower() == 'not published':
            self.conditions[self.signal_when_cfg["signal_when"]]["satisfied"] = True
            
            if self.signal_when_cfg["safety_critical"]:
                self.signal_when_is_safe = False
            if self.signal_when_cfg["autonomy_critical"]:
                self.signal_when_is_auto = False
            if self.signal_when_cfg["default_notifications"] and self.signal_when_cfg["safety_critical"]:
                self.event_callback("SAFETY CRITICAL: Topic %s is not published anymore" % self.topic_name, "error")
            elif self.signal_when_cfg["default_notifications"]:
                self.event_callback("Topic %s is not published anymore" % self.topic_name, "warn")
            if _exec and not self.signal_when_cfg["repeat_exec"]:
                self.execute(process_indices=self.signal_when_cfg["process_indices"])
        
        
    def run(self):
        # if the topic was not published initially then no monitor is running
        # but, maybe now it is published
        if not self.is_instantiated:
            if not self._instantiate_monitors():
                return
            else:
                self.is_instantiated = True
                
        def cb(_):
            self.set_not_published()

        def repeat_cb(_):
            if self.signal_when_cfg["signal_when"].lower() == 'not published':
                self.execute(process_indices=self.signal_when_cfg["process_indices"])

        timer = None
        timer_repeat = None
        while not self._killed_event.isSet():
            while not self._stop_event.isSet():
                
                self.thread_is_safe = self.signal_when_is_safe and self.lambdas_are_safe
                if not self.independent_tags:
                    self.thread_is_auto = self.thread_is_safe and self.signal_when_is_auto and self.lambdas_are_auto
                else:
                    self.thread_is_auto = self.signal_when_is_auto and self.lambdas_are_auto
                
                # check it is still published (None if not)
                if self.hz_monitor is not None:
                    rate = self.hz_monitor.get_hz()
                    
                    if rate is None and self.is_topic_published:
                        self.is_topic_published = False
    
                        timer = rospy.Timer(rospy.Duration.from_sec(self.signal_when_cfg["timeout"]), cb, oneshot=True)
                        
                        if self.signal_when_cfg["repeat_exec"]:
                            timer_repeat = rospy.Timer(rospy.Duration.from_sec(self.signal_when_cfg["timeout"]), repeat_cb, oneshot=False)
    
                    if rate is not None:
                        self.is_topic_published = True
                        
                        if self.signal_when_cfg["signal_when"].lower() == 'not published':
                            self.conditions[self.signal_when_cfg["signal_when"]]["satisfied"] = False
                            
                        if self.signal_when_cfg["safety_critical"]:
                            self.signal_when_is_safe = True

                        if self.signal_when_cfg["autonomy_critical"]:
                            self.signal_when_is_auto = True
    
                        if timer is not None:
                            timer.shutdown()
                            timer = None
                        
                        if self.signal_when_cfg["repeat_exec"]:
                            if timer_repeat is not None:
                                timer_repeat.shutdown()
                                timer_repeat = None

                time.sleep(0.3)
            time.sleep(1)
            

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
                                self.event_callback("SAFETY CRITICAL: Expression '%s' for %s seconds on topic %s satisfied" % (expr, config["timeout"], self.topic_name), "error", msg)
                            else:
                                self.event_callback("Expression '%s' for %s seconds on topic %s satisfied" % (expr, config["timeout"], self.topic_name), "warn", msg)
                        
                        if not config["repeat_exec"]:
                            self.execute(msg, config["process_indices"])
                
                self._lock.acquire()
                self.sat_expressions_timer.update({expr: rospy.Timer(rospy.Duration.from_sec(config["timeout"]), cb, oneshot=True)})
                self._lock.release()
            
            if config["repeat_exec"]:
                if not expr in self.sat_expr_repeat_timer:
                    
                    def repeat_cb(_):
                        process_lambda, self.sat_expr_repeat_timer = ProcessLambda(self.sat_expr_repeat_timer)
                        if process_lambda:     
                            self.execute(msg, config["process_indices"])
                            self.sat_expr_repeat_timer = self.kill_timer(self.sat_expr_repeat_timer, config["expr"]) 
                            
                    self._lock.acquire()
                    self.sat_expr_repeat_timer.update({expr: rospy.Timer(rospy.Duration.from_sec(config["timeout"]), repeat_cb, oneshot=True)})
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
            #self.execute(msg, self.signal_when_cfg["process_indices"])
                
                
    def kill_timer(self, timer_dict, expr):
        self._lock.acquire()
        timer_dict[expr].shutdown()
        timer_dict.pop(expr)
        self._lock.release()
        return timer_dict
            
            
    def execute(self, msg=None, process_indices=None):
        if self.processes:
            rospy.sleep(0.1) # needed when using slackeros
            self.executor.execute(msg, process_indices)
            
            
    def stop_monitor(self):
        self.active = False
        self._stop_event.set()
        

    def start_monitor(self):
        self.active = True
        self._stop_event.clear()
        

    def kill_monitor(self):
        self.stop_monitor()
        self._killed_event.set()
##########################################################################################