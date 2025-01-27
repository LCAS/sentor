#!/usr/bin/env python
"""
@author: Adam Binch (abinch@sagarobotics.com)
"""
##########################################################################################
from sentor.TopicMapper import TopicMapper
from sentor.TopicMapServer import TopicMapServer

import signal
import rospy
import time
import yaml
import os


def __signal_handler(signum, frame):
    def kill_mappers():
        for topic_mapper in topic_mappers:
            topic_mapper.stop_mapping()
        topic_map_server.stop()
    def join_mappers():
        for topic_mapper in topic_mappers:
            topic_mapper.join()
    kill_mappers()
    join_mappers()
    print("stopped.")
    os._exit(signal.SIGTERM)
##########################################################################################
    

##########################################################################################
if __name__ == "__main__":
    signal.signal(signal.SIGINT, __signal_handler)
    rospy.init_node("topic_mapper")

    config_file = rospy.get_param("~config_file", "")
    try:
        items = [yaml.load(file(item, 'r')) for item in config_file.split(',')]
        topics = [item for sublist in items for item in sublist]
    except Exception as e:
        rospy.logerr("No configuration file provided: %s" % e)
        topics = []
    
    topic_mappers = []
    print("Mapping topics:")
    for i, topic in enumerate(topics):
        try:
            topic_name = topic["name"]
        except Exception as e:
            rospy.logerr("topic name is not specified for entry %s" % topic)
            continue

        include = True
        if "include" in topic.keys():
            include = topic["include"]

        if include:
            topic_mappers.append(TopicMapper(topic, i))
            
    time.sleep(1)
    
    map_pub_rate = rospy.get_param("~map_pub_rate", 0) 
    map_plt_rate = rospy.get_param("~map_plt_rate", 0) 
    topic_map_server = TopicMapServer(topic_mappers, map_pub_rate, map_plt_rate)

    # start mapping
    for topic_mapper in topic_mappers:
        topic_mapper.start()

    rospy.spin()
##########################################################################################