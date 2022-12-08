#!/usr/bin/env python
"""
Created on Fri Dec  6 08:51:15 2019

@author: Adam Binch (abinch@sagarobotics.com)
"""
#####################################################################################
from __future__ import division
import rospy, rostopic
from std_msgs.msg import Bool
from sentor.msg import Tag, TagArray
from std_srvs.srv import SetBool, SetBoolResponse
from threading import Event


class SafetyMonitor(object):
    
    
    def __init__(self, topic, event_msg, attr, crit_key, srv, event_cb, invert=False):
        
        self.event_msg = event_msg + ": "
        self.attr = attr
        self.crit_key = crit_key
        self.event_cb = event_cb
        self.invert = invert
        
        self.topic_monitors = []
        self.bad_monitors = []
        
        self.timer = None
        self.safe_operation = False        
        self.safe_msg_sent = False
        self.unsafe_msg_sent = False
        self.auto = False
        
        self._stop_event = Event()

        timeout = rospy.get_param("~safe_operation_timeout", 10.0)
        rate = rospy.get_param("~safety_pub_rate", 10.0)
        self.auto_tagging = rospy.get_param("~auto_safety_tagging", True)
        
        auto_topic = rospy.get_param("~auto_topic", "auto_mode")
        auto_topic = "/" + auto_topic if auto_topic[0] != "/" else auto_topic

        if timeout > 0:
            self.timeout = timeout
        else:
            self.timeout = 0.1

        self.event_cb(self.event_msg + "FALSE", "error")
        self.unsafe_msg_sent = True
        
        _, real_topic, _ = rostopic.get_topic_class(auto_topic, blocking=False)
        if real_topic is not None:
            rospy.Subscriber(auto_topic, Bool, self.auto_mode_cb)
            self.auto_takeover_pub = rospy.Publisher("/sentor/auto_takeover_reason", TagArray, queue_size=5)
        else:
            rospy.logwarn("Auto mode topic {} is not published".format(auto_topic))

        self.safety_pub = rospy.Publisher(topic, Bool, queue_size=10)
        rospy.Timer(rospy.Duration(1.0/rate), self.safety_pub_cb)
        
        rospy.Service("/sentor/" + srv, SetBool, self.srv_cb)


    def register_monitors(self, topic_monitor):
        self.topic_monitors.append(topic_monitor)
        
        
    def auto_mode_cb(self, msg):
        self.auto = msg.data
        
        
    def safety_pub_cb(self, event=None):
        
        if not self._stop_event.isSet():

            if self.topic_monitors:
                threads_are_safe = [getattr(monitor, self.attr) for monitor in self.topic_monitors if monitor.active]
                self.bad_monitors = [i for i, item in enumerate(threads_are_safe) if not item]
                
                if self.auto_tagging and all(threads_are_safe) and self.timer is None:
                    self.timer = rospy.Timer(rospy.Duration.from_sec(self.timeout), self.timer_cb, oneshot=True)
                    
                if not all(threads_are_safe):
                    if self.timer is not None:
                        self.timer.shutdown()
                        self.timer = None

                    self.safe_operation = False                        
                    if not self.unsafe_msg_sent:
                        self.event_cb(self.event_msg + "FALSE", "error")
                        self.auto_takeover_cb()
                        self.safe_msg_sent = False
                        self.unsafe_msg_sent = True

                if self.invert:
                    self.safety_pub.publish(Bool(not self.safe_operation))       
                else:
                    self.safety_pub.publish(Bool(self.safe_operation))


    def timer_cb(self, event=None):
        
        self.safe_operation = True
        if not self.safe_msg_sent:
            self.event_cb(self.event_msg + "TRUE", "info")
            self.safe_msg_sent = True
            self.unsafe_msg_sent = False
            
            
    def auto_takeover_cb(self):
        
        if self.auto:
            tags = TagArray()
            for i in self.bad_monitors:
                monitor = self.topic_monitors[i]
                
                for expr in monitor.conditions:
                    if monitor.conditions[expr][self.crit_key]:
                        tag = Tag()
                        tag.type = self.crit_key
                        tag.tag = monitor.conditions[expr]["tags"]
                        tags.tags.append(tag)
            
            if tags.tags:             
                self.auto_takeover_pub.publish(tags)
                                       
        
    def srv_cb(self, req):
        
        self.safe_operation = req.data        
        
        ans = SetBoolResponse()
        ans.success = True
        ans.message = self.event_msg + "{}".format(req.data)
        
        return ans
        
        
    def stop_monitor(self):
        self._stop_event.set()


    def start_monitor(self):
        self._stop_event.clear()
#####################################################################################