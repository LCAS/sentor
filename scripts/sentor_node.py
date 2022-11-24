#!/usr/bin/env python
"""
@author: Adam Binch (abinch@sagarobotics.com)
@author: Francesco Del Duchetto (FDelDuchetto@lincoln.ac.uk)
"""
##########################################################################################
from __future__ import division
import signal, rospy, yaml, os

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
        
        self.safety_monitor = SafetyMonitor("safe_operation", "SAFE OPERATION", "thread_is_safe", "safety_critical", 
                                            "set_safety_tag", self.event_callback)
        self.autonomy_monitor = SafetyMonitor("pause_autonomous_operation", "SAFE AUTONOMOUS OPERATION", "thread_is_auto", 
                                              "autonomy_critical", "set_autonomy_tag", self.event_callback, invert=True)
        self.multi_monitor = MultiMonitor()
        
        self.event_pub = rospy.Publisher('/sentor/event', String, queue_size=10)
        self.rich_event_pub = rospy.Publisher('/sentor/rich_event', SentorEvent, queue_size=10)
        
        self.topics = []
        self.topic_monitors = []
        self.topic_monitors_all = []
        self.tags_in_use = []
        
        config_file = rospy.get_param("~config_file", "")
        tags = rospy.get_param("~topic_tags", "")
        tags = tags.split(",")
        
        if config_file:
            self.load_topics(config_file, tags)
            self.instantiate()
        
        rospy.Service('/sentor/load_monitors', Client, self.load_monitors)
        rospy.Service('/sentor/stop_monitors', Client, self.stop_monitoring)
        rospy.Service('/sentor/start_monitors', Client, self.start_monitoring)
        
        signal.signal(signal.SIGINT, self.__signal_handler)
        
        rospy.spin()
        
        
    def load_topics(self, config_file, requested_tags=[]):
        self.topics = []
        self.current_tags = []
        
        try:
            items = [yaml.safe_load(open(item, 'r')) for item in config_file.split(',')]
            self.topics = [item for sublist in items for item in sublist]
            
            if requested_tags and requested_tags[0]:
                filtered_topics = []
                for topic in self.topics:
                    if "topic_tags" in topic:
                        for tag in set(requested_tags):
                            if tag in topic["topic_tags"]:
                                filtered_topics.append(topic)
                                self.current_tags.append(tag)

                self.topics = filtered_topics
            
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
                
            if any(tag in topic_tags for tag in self.tags_in_use):
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
            
        self.tags_in_use.extend(self.current_tags)
        self.tags_in_use = list(set(self.tags_in_use))
            
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
        
        success = False
        for monitor in self.topic_monitors_all:
            if req.topic_tags and req.topic_tags[0]:
                if any(tag in monitor.topic_tags for tag in req.topic_tags):
                    monitor.stop_monitor()
                    success = True
            else:
                monitor.stop_monitor()
                success = True
           
        rospy.logwarn("sentor node stopped monitoring topics")
        return success
        
    
    def start_monitoring(self, req):
        
        success = False
        for monitor in self.topic_monitors_all:
            if req.topic_tags and req.topic_tags[0]:
                if any(tag in monitor.topic_tags for tag in req.topic_tags):
                    monitor.start_monitor()
                    success = True
            else:
                monitor.start_monitor()
                success = True
        
        rospy.logwarn("sentor node started monitoring topics")
        return success
    
    
    def __signal_handler(self, signum, frame):

        def kill_monitors():
            for topic_monitor in self.topic_monitors:
                topic_monitor.kill_monitor()
    
            self.safety_monitor.stop_monitor()
            self.autonomy_monitor.stop_monitor()
            self.multi_monitor.stop_monitor()
    
        def join_monitors():
            for topic_monitor in self.topic_monitors:
                topic_monitor.join()
    
        kill_monitors()
        join_monitors()
        print("stopped.")
        os._exit(signal.SIGTERM)
##########################################################################################


##########################################################################################
if __name__ == "__main__":
    
    rospy.init_node("sentor")
    sentor()
##########################################################################################