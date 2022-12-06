#!/usr/bin/env python
"""
@author: Adam Binch (abinch@sagarobotics.com)
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
"""
##########################################################################################
from __future__ import division
import signal, rospy, yaml, os, copy

from sentor.TopicMonitor import TopicMonitor
from sentor.SafetyMonitor import SafetyMonitor
from sentor.MultiMonitor import MultiMonitor

from std_msgs.msg import String
from sentor.msg import SentorEvent
from sentor.msg import MonitorArray
from sentor.srv import Client
##########################################################################################


##########################################################################################
class sentor(object):
    
    
    def __init__(self):

        self.topics = []
        self.topic_monitors = []
        self.topic_monitors_all = []
        self.tags_in_use = {}
        
        config_file = rospy.get_param("~config_file", "")
        tags = rospy.get_param("~topic_tags", "")

        self.event_pub = rospy.Publisher('/sentor/event', String, queue_size=10)
        self.rich_event_pub = rospy.Publisher('/sentor/rich_event', SentorEvent, queue_size=10)
        
        self.safety_monitor = SafetyMonitor("safe_operation", "SAFE OPERATION", "thread_is_safe", "safety_critical", 
                                            "set_safety_tag", self.event_callback)
        self.autonomy_monitor = SafetyMonitor("pause_autonomous_operation", "SAFE AUTONOMOUS OPERATION", "thread_is_auto", 
                                              "autonomy_critical", "set_autonomy_tag", self.event_callback, invert=True)
        self.multi_monitor = MultiMonitor()
        
        if config_file:
            self.load_topics(config_file, tags)
            self.instantiate()
        
        rospy.Service('/sentor/load_monitors', Client, self.load_monitors)
        rospy.Service('/sentor/stop_monitors', Client, self.stop_monitoring)
        rospy.Service('/sentor/start_monitors', Client, self.start_monitoring)
        rospy.Service('/sentor/kill_monitors', Client, self.kill_monitors_cb)
        
        signal.signal(signal.SIGINT, self.__signal_handler)
        
        rospy.spin()
        
        
    def load_topics(self, config_file, requested_tags=""):

        self.config_file = config_file
        requested_tags = list(set(requested_tags.split(",")))
        self.topics = []
        self.current_tags = []
        
        try:
            items = [yaml.safe_load(open(item, 'r')) for item in config_file.split(',')]
            self.topics = [item for sublist in items for item in sublist]
            
            if requested_tags and requested_tags[0]:
                filtered_topics = []
                for topic in self.topics:
                    if "topic_tags" in topic:
                        for tag in requested_tags:
                            if tag in topic["topic_tags"]:
                                filtered_topics.append(topic)
                                self.current_tags.append(tag)
                self.topics = filtered_topics
                self.current_tags = list(set(self.current_tags))
            
        except Exception as e:
            rospy.logerr("Error loading configuration file: {}".format(e))
            
            
    def instantiate(self):
        self.topic_monitors = []
        
        print("Monitoring topics:")
        for i, topic in enumerate(self.topics):
            
            include = True
            if 'include' in topic:
                include = topic['include']
                
            if not include:
                continue
            
            try:
                topic_name = topic["name"]
            except Exception:
                rospy.logerr("topic name is not specified for entry %s" % topic)
                continue

            topic_tags = []
            if 'topic_tags' in topic:
                topic_tags = topic['topic_tags']

            if self.config_file in self.tags_in_use:    
                if any(tag in topic_tags for tag in self.tags_in_use[self.config_file]):
                    continue
    
            rate = 0
            N = 0
            signal_when = {}
            signal_lambdas = []
            processes = []
            timeout = 0
            default_notifications = True
            
            if 'rate' in topic:
                rate = topic['rate']
            if 'N' in topic:
                N = int(topic['N'])
            if 'signal_when' in topic:
                signal_when = topic['signal_when']
            if 'signal_lambdas' in topic:
                signal_lambdas = topic['signal_lambdas']
            if 'execute' in topic:
                processes = topic['execute']
            if 'timeout' in topic:
                timeout = topic['timeout']
            if 'default_notifications' in topic:
                default_notifications = topic['default_notifications']
    
            topic_monitor = TopicMonitor(topic_name, rate, N, signal_when, signal_lambdas, processes, 
                                         timeout, default_notifications, self.event_callback, topic_tags)
    
            self.topic_monitors.append(topic_monitor)
            self.topic_monitors_all.append(topic_monitor)
            
            self.safety_monitor.register_monitors(topic_monitor)
            self.autonomy_monitor.register_monitors(topic_monitor)
            self.multi_monitor.register_monitors(topic_monitor)

        if self.config_file not in self.tags_in_use:
            self.tags_in_use[self.config_file] = self.current_tags
        else:
            self.tags_in_use[self.config_file].extend(self.current_tags)
            
        tags = list(set(self.tags_in_use[self.config_file])) 
        self.tags_in_use[self.config_file] = tags
           
        rospy.sleep(1.0)
        for topic_monitor in self.topic_monitors:
            topic_monitor.start()
        
        
    def event_callback(self, string, type, msg="", nodes=[], topic=""):
        
        if type == "info":
            rospy.loginfo(string + '\n' + str(msg))
        elif type == "warn":
            rospy.logwarn(string + '\n' + str(msg))
        elif type == "error":
            rospy.logerr(string + '\n' + str(msg))
    
        self.event_pub.publish(String("%s: %s" % (type, string)))
    
        event = SentorEvent()
        event.header.stamp = rospy.Time.now()
        event.level = SentorEvent.INFO if type == "info" else SentorEvent.WARN if type == "warn" else SentorEvent.ERROR
        event.message = string
        event.nodes = nodes
        event.topic = topic
        self.rich_event_pub.publish(event)
        
        
    def load_monitors(self, req):
        
        try:
            self.load_topics(req.config, req.topic_tags)
            self.instantiate()
            return True
        except Exception as e:
            rospy.logerr(e)
            return False
        
        
    def stop_monitoring(self, req):

        topic_tags = list(set(req.topic_tags.split(",")))
        
        success = False
        for monitor in self.topic_monitors_all:
            if topic_tags and topic_tags[0]:
                if any(tag in monitor.topic_tags for tag in topic_tags):
                    monitor.stop_monitor()
                    success = True
            else:
                monitor.stop_monitor()
                success = True
           
        rospy.logwarn("sentor node stopped monitoring topics")
        return success
        
    
    def start_monitoring(self, req):

        topic_tags = list(set(req.topic_tags.split(",")))
        
        success = False
        for monitor in self.topic_monitors_all:
            if topic_tags and topic_tags[0]:
                if any(tag in monitor.topic_tags for tag in topic_tags):
                    monitor.start_monitor()
                    success = True
            else:
                monitor.start_monitor()
                success = True
        
        rospy.logwarn("sentor node started monitoring topics")
        return success


    def kill_monitors_cb(self, req):
        
        topic_tags = list(set(req.topic_tags.split(",")))
        success = False
        monitors_to_kill = []
        tags_to_kill = []

        if topic_tags and topic_tags[0]:
            for monitor in self.topic_monitors_all:
                if any(tag in monitor.topic_tags for tag in topic_tags):
                    monitors_to_kill.append(monitor)
                    tags_to_kill.extend(monitor.topic_tags)
                    success = True

            old_tags = copy.deepcopy(self.tags_in_use)
            self.tags_in_use = {}
            for key in old_tags:
                self.tags_in_use[key] = [tag for tag in old_tags[key] if tag not in tags_to_kill]
        else:
            monitors_to_kill = self.topic_monitors_all
            self.tags_in_use = {}
            success = True

        self.kill_monitors(monitors_to_kill)
        self.topic_monitors_all = [monitor for monitor in self.topic_monitors_all if monitor not in monitors_to_kill]

        self.init_monitors(self.topic_monitors_all)

        rospy.logwarn("sentor node killed monitors with tags '{}'".format(req.topic_tags))
        return success

        
    def kill_monitors(self, topic_monitors):

        for topic_monitor in topic_monitors:
            topic_monitor.kill_monitor()

        for topic_monitor in topic_monitors:
            topic_monitor.join()


    def init_monitors(self, topic_monitors):

        self.safety_monitor.topic_monitors = []
        self.autonomy_monitor.topic_monitors = []
        self.multi_monitor.topic_monitors = []

        for topic_monitor in topic_monitors:
            self.safety_monitor.register_monitors(topic_monitor)
            self.autonomy_monitor.register_monitors(topic_monitor)
            self.multi_monitor.register_monitors(topic_monitor)


    def __signal_handler(self, signum, frame):

        self.safety_monitor.stop_monitor()
        self.autonomy_monitor.stop_monitor()
        self.multi_monitor.stop_monitor()
    
        self.kill_monitors(self.topic_monitors_all)
        print("stopped.")
        os._exit(signal.SIGTERM)
##########################################################################################


##########################################################################################
if __name__ == "__main__":
    
    rospy.init_node("sentor")
    sentor()
##########################################################################################