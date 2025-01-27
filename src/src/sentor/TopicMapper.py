#!/usr/bin/env python
"""
Created on Tue Feb 25 08:55:41 2020

@author: Adam Binch (abinch@sagarobotics.com)
"""
##########################################################################################
from __future__ import division
from threading import Thread, Event
from cv2 import imread

import rospy, rostopic, tf
import numpy as np, numpy
import math
import yaml, os, subprocess


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
class TopicMapper(Thread):
    
    
    def __init__(self, config, thread_num):
        Thread.__init__(self)
        
        self.config = config
        self.thread_num = thread_num
        self.topic_name = config["name"]
        
        self.map_frame = "map"
        if "map_frame" in config:
            self.map_frame = config["map_frame"]
            
        self.base_frame = "base_link"
        if "base_frame" in config:
            self.base_frame = config["base_frame"]
            
        self.config["map_frame"] = self.map_frame
        self.config["base_frame"] = self.base_frame
        
        self.set_limits()
        self.config["limits"] = [self.x_min, self.x_max, self.y_min, self.y_max]
        
        self.x_bins = np.arange(self.x_min, self.x_max, config["resolution"])
        self.y_bins = np.arange(self.y_min, self.y_max, config["resolution"])
        
        self.nx = self.x_bins.shape[0] + 1
        self.ny = self.y_bins.shape[0] + 1
        
        self.shape = [self.nx, self.ny]
        self.config["shape"] = self.shape
        
        self.init_map()
        
        self.stat = self.set_stat()
        
        self._stop_event = Event()

        self.tf_listener = tf.TransformListener()          
        
        self.is_instantiated = self.instantiate()
        
        
    def set_limits(self):
        
        if "map" in self.config:
            map_config = yaml.load(file(self.config["map"], 'r'))
            dims = imread(os.path.dirname(self.config["map"]) + "/" + map_config["image"]).shape
            
            self.x_min, self.x_max = map_config["origin"][0], map_config["origin"][0] + (map_config["resolution"] * dims[0]) 
            self.y_min, self.y_max = map_config["origin"][1], map_config["origin"][1] + (map_config["resolution"] * dims[1]) 
            
        if "limits" in self.config:
            self.x_min, self.x_max = self.config["limits"][:2]
            self.y_min, self.y_max = self.config["limits"][2:]
            
        if "map" not in self.config and "limits" not in self.config:
            rospy.logerr("No topic map limits specified")
            exit()
        
        
    def init_map(self):
        
        self.obs = np.zeros((self.nx, self.ny))
        self.map = np.zeros((self.nx, self.ny))  
        self.map[:] = np.nan
        
        if self.config["stat"] == "stdev":
            self.wma = np.zeros((self.nx, self.ny))
            self.wma[:] = np.nan
            
            
    def set_stat(self):
        
        if self.config["stat"] == "mean":
            stat = self._mean
            
        elif self.config["stat"] == "sum":
            stat = self._sum
            
        elif self.config["stat"] == "min":
            stat = self._min
            
        elif self.config["stat"] == "max":
            stat = self._max
            
        elif self.config["stat"] == "stdev":
            stat = self._stdev
            
        else:
            rospy.logerr("Statistic of type '{}' not supported".format(self.config["stat"]))
            exit()
            
        return stat
    
    
    def _mean(self, z, N):
        return self.weighted_mean(z, self.topic_arg, N)
    
    
    def _sum(self, z, N):
        return z + self.topic_arg
    
    
    def _min(self, z, N):
        return np.min([z, self.topic_arg])
    
    
    def _max(self, z, N):
        return np.max([z, self.topic_arg])
    
    
    def _stdev(self, z, N):
        wm = self.wma[self.ix, self.iy]
        if np.isnan(wm): wm=0

        wm = self.weighted_mean(wm, self.topic_arg, N)
        self.wma[self.ix, self.iy] = wm
            
        return np.sqrt(self.weighted_mean(z**2, (wm-self.topic_arg)**2, N))
    
    
    def weighted_mean(self, m, x, N):
        return (1/N) * ((m * (N-1)) + x)
            
            
    def instantiate(self):
        
        try:
            msg_class, real_topic, _ = rostopic.get_topic_class(self.topic_name, blocking=False)
            topic_type, _, _ = rostopic.get_topic_type(self.topic_name, blocking=False)
        except rostopic.ROSTopicException:
            rospy.logerr("Topic {} type cannot be determined, or ROS master cannot be contacted".format(self.topic_name))
            return False

        if real_topic is None:
            rospy.logerr("Topic {} is not published".format(self.topic_name))
            return False
        
        print("Mapping topic arg "+ bcolors.OKGREEN + self.config["arg"] + bcolors.ENDC +" on topic "+ bcolors.OKBLUE + self.topic_name + bcolors.ENDC + '\n')
        
        rate = 0
        if "rate" in self.config:
            rate = self.config["rate"]
            
        if rate > 0:
            COMMAND_BASE = ["rosrun", "topic_tools", "throttle"]
            subscribed_topic = "/sentor/mapping/" + str(self.thread_num) + real_topic
            
            command = COMMAND_BASE + ["messages", real_topic, str(rate), subscribed_topic]
            subprocess.Popen(command, stdout=open(os.devnull, "wb"))
        else:
            subscribed_topic = real_topic
            
        self.throttle_val = 0
        if "N" in self.config:
            self.throttle_val = int(self.config["N"])
        
        self.throttle = self.throttle_val
        if self.throttle_val <= 0:
            cb = self.topic_cb
        else:
            cb = self.topic_cb_throttled
            
        rospy.Subscriber(subscribed_topic, msg_class, cb)
            
        return True
            
 
    def topic_cb(self, msg):
        
        if not self._stop_event.isSet():    
            
            try:
                x, y = self.get_transform()
            except: 
                rospy.logwarn("Failed to get a tf transform between {} and {}".format(self.map_frame, self.base_frame))
                return
                
            if self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max:  
                valid_arg = self.process_arg(msg)
                
                if valid_arg:
                    self.update_map(x, y)
                    
                    
    def topic_cb_throttled(self, msg):
        
        if (self.throttle % self.throttle_val) == 0:
            self.topic_cb(msg)
            self.throttle = 1
        else:
            self.throttle += 1

        
    def get_transform(self):
        
        now = rospy.Time(0)
        self.tf_listener.waitForTransform(self.map_frame, self.base_frame, now, rospy.Duration(1.0))
        (trans,rot) = self.tf_listener.lookupTransform(self.map_frame, self.base_frame, now)
        
        return trans[0], trans[1]
        
        
    def process_arg(self, msg):
        
        try:
            self.topic_arg = eval(self.config["arg"])
        except Exception as e:
            rospy.logwarn("Exception while evaluating '{}': {}".format(self.config["arg"], e))
            return False
            
        valid_arg = True
        if isinstance(self.topic_arg, bool):
            self.topic_arg = int(self.topic_arg) 
        elif not isinstance(self.topic_arg, float) and not isinstance(self.topic_arg, int):
            rospy.logwarn("Topic arg '{}' of {} on topic '{}' cannot be processed".format(self.config["arg"], type(self.topic_arg), self.topic_name))
            valid_arg = False
        
        return valid_arg
        
        
    def update_map(self, x, y):

        ix = np.digitize(x, self.x_bins)
        iy = np.digitize(y, self.y_bins)     
        self.ix = ix
        self.iy = iy
        
        self.obs[ix, iy] += 1        
        N = self.obs[ix, iy]
        
        z = self.map[ix, iy]
        if np.isnan(z): z=0
        
        z = self.stat(z, N)
        self.map[ix, iy] = z        
        
                        
    def stop_mapping(self):
        self._stop_event.set()
        
        
    def start_mapping(self):
        self._stop_event.clear()
##########################################################################################