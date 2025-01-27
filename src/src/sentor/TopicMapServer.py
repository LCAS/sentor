#!/usr/bin/env python
"""
Created on Mon Mar  2 10:57:11 2020

@author: Adam Binch (abinch@sagarobotics.com)
"""
##########################################################################################
from __future__ import division
import rospy, numpy as np
import os, uuid, pickle, yaml
import matplotlib.pyplot as plt

from threading import Event
from sentor.msg import TopicMap, TopicMapArray
from sentor.srv import GetTopicMaps, GetTopicMapsResponse
from std_srvs.srv import Trigger, TriggerResponse
from std_srvs.srv import Empty, EmptyResponse


class TopicMapServer(object):
    

    def __init__(self, topic_mappers, map_pub_rate, map_plt_rate):
        
        self.base_dir = os.path.join(os.path.expanduser("~"), ".sentor_maps")     
        if not os.path.exists(self.base_dir):
            os.mkdir(self.base_dir)    
        
        self.topic_mappers = topic_mappers

        self._stop_event = Event()

        rospy.Service("/sentor/write_maps", Trigger, self.write_maps)               
        rospy.Service("/sentor/get_maps", GetTopicMaps, self.get_maps)               
        rospy.Service("/sentor/clear_maps", Empty, self.clear_maps)   
        rospy.Service("/sentor/stop_mapping", Empty, self.stop_mapping)   
        rospy.Service("/sentor/start_mapping", Empty, self.start_mapping)  
        
        if map_pub_rate > 0:            
            if map_pub_rate > 1:
                map_pub_rate = 1                
            self.maps_pub = rospy.Publisher('/sentor/topic_maps', TopicMapArray, queue_size=10)
            rospy.Timer(rospy.Duration(1.0/map_pub_rate), self.publish_maps)
        
#        if map_plt_rate > 0:
#            if map_plt_rate > 1:
#                map_plt_rate = 1 
#            rospy.Timer(rospy.Duration(1.0/map_plt_rate), self.plot_maps)
            
            
    def write_maps(self, req):
    
        message = "Saving maps: "
        for mapper in self.topic_mappers:
            if mapper.is_instantiated:

                map_dir = os.path.join(self.base_dir, str(uuid.uuid4()))
                os.mkdir(map_dir)
                
                pickle.dump(mapper.map, open(map_dir + "/topic_map.pkl", "wb"))
            
                with open(map_dir + "/config.yaml",'w') as f:
                    yaml.dump(mapper.config, f, default_flow_style=False)                
                    
                message = message + map_dir + " "
            
        ans = TriggerResponse()
        ans.success = True
        ans.message = message
        return ans
        
        
    def get_maps(self, req):
        
        topic_maps = TopicMapArray()
        topic_maps = self.fill_msg(topic_maps)
        
        ans = GetTopicMapsResponse()
        ans.topic_maps = topic_maps
        ans.success = True
        return ans
        
        
    def clear_maps(self, req):
        
        for mapper in self.topic_mappers:
            if mapper.is_instantiated:
                mapper.init_map()
            
        ans = EmptyResponse()
        return ans
        
        
    def stop_mapping(self, req):
        self.stop()
        
        rospy.logwarn("topic_mapping_node stopped mapping")
        ans = EmptyResponse()
        return ans
        

    def start_mapping(self, req):
        self.start()
        
        rospy.logwarn("topic_mapping_node started mapping")
        ans = EmptyResponse()
        return ans
        
        
    def publish_maps(self, event=None):
        
        if not self._stop_event.isSet():
            
            topic_maps = TopicMapArray()
            topic_maps = self.fill_msg(topic_maps)
            self.maps_pub.publish(topic_maps)
            
            
    def plot_maps(self, event=None):
        # broke after move to ubuntu 18
        
        if not self._stop_event.isSet():
            
            _id = 0
            for mapper in self.topic_mappers:
                if mapper.is_instantiated:
                
                    fig_id = "thread " + str(_id) + ": " + mapper.topic_name + " " + mapper.config["arg"] + " " + mapper.config["stat"] 
                    
                    _map = mapper.map
                    masked_map = np.ma.array(_map, mask=np.isnan(_map))
                    
                    plt.pause(0.1)
                    plt.figure(fig_id); plt.clf()
                    plt.imshow(masked_map.T, interpolation="spline16", origin="lower", 
                               extent=mapper.config["limits"])
                    plt.colorbar()
                    plt.gca().set_aspect("equal", adjustable="box")
                    plt.tight_layout()
    
                _id += 1
        
        
    def fill_msg(self, topic_maps):
        
        for mapper in self.topic_mappers:
            if mapper.is_instantiated:
                    
                map_msg = TopicMap()
                map_msg.header.stamp = rospy.Time.now()
                map_msg.header.frame_id = mapper.map_frame
                map_msg.child_frame_id = mapper.base_frame
                map_msg.topic_name = mapper.topic_name
                map_msg.topic_arg = mapper.config["arg"]
                map_msg.stat = mapper.config["stat"]
                map_msg.resolution = mapper.config["resolution"]
                map_msg.shape = mapper.shape
                map_msg.limits = mapper.config["limits"]
    
                topic_map = np.ndarray.tolist(np.ravel(mapper.map))
                map_msg.topic_map = topic_map
            
                topic_maps.topic_maps.append(map_msg)
                
        return topic_maps
    
    
    def stop(self):

        self._stop_event.set()    
        
        for mapper in self.topic_mappers:
            if mapper.is_instantiated:
                mapper.stop_mapping()
                
        
    def start(self):
        
        self._stop_event.clear()      
        
        for mapper in self.topic_mappers:
            if mapper.is_instantiated:
                mapper.start_mapping()
##########################################################################################