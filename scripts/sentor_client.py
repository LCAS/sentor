#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  1 09:25:27 2022

@author: Adam Binch (abinch@sagarobotics.com)
"""
###################################################################################################################
import rospy, sys, argparse
from sentor.srv import Client, ClientRequest

modes = {}
modes["load"] = "/sentor/load_monitors"
modes["stop"] = "/sentor/stop_monitors"
modes["start"] = "/sentor/start_monitors"
modes["kill"] = "/sentor/kill_monitors"


class sentor_client(object):


    def __init__(self, mode, config, tags, spin):

        self.tags = tags

        self.call_service(modes[mode], config, tags)

        if spin and mode == "load":
            rospy.on_shutdown(self._on_node_shutdown)
            rospy.spin()


    def call_service(self, name, config, tags):

        print("Calling service...")
        print("\tname: {}".format(name))
        print("\tconfig: {}".format(config))
        print("\ttags: {}".format(tags))
    
        rospy.wait_for_service(name, timeout=10.0)
        try:
            s = rospy.ServiceProxy(name, Client)
            req = ClientRequest()
            req.config = config
            req.topic_tags = tags
            resp = s.call(req)
            rospy.loginfo(resp)
        except rospy.ServiceException as e:
            print("Service call failed: {}".format(e))


    def _on_node_shutdown(self):
            self.call_service(modes["kill"], "", self.tags)
###################################################################################################################
    
    
###################################################################################################################
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", type=str,
                        help="(str) load, stop, start or kill (monitors). Required.")
    parser.add_argument("--config", type=str, default="",
                        help="(str) sentor config file. Required if mode=load.")
    parser.add_argument("--topic_tags", type=str, default="",
                        help="(str) topic tags used to load/stop/start/kill individual monitors. Separate multiple topic tags using commas. Optional.")
    parser.add_argument("--spin", type=lambda x: (str(x).lower() == "true"), default=False, 
                        help="(bool) Spin the client and kill loaded monitors on shutdown. Default=False")
    

    rospy.init_node("sentor_client", anonymous=True)

    args = parser.parse_args()
    if args.mode == "load" and not args.config:
        rospy.logerr("--config CONFIG  (str) sentor config file. Required if mode=load.")
        sys.exit(1)

    sentor_client(args.mode, args.config, args.topic_tags, args.spin)
###################################################################################################################