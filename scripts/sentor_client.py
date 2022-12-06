#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  1 09:25:27 2022

@author: Adam Binch (abinch@sagarobotics.com)
"""
###################################################################################################################
import rospy, sys, argparse
from sentor.srv import Client, ClientRequest


def usage():
    print("\nLoads/stops/starts topic monitors:")
    print("\nFor loading monitors:")
    print("\t rosrun sentor sentor_client.py load CONFIG TOPIC_TAG_1,TOPIC_TAG_2,TOPIC_TAG_N")
    print("\nFor stopping monitors:")
    print("\t rosrun sentor sentor_client.py stop TOPIC_TAG_1,TOPIC_TAG_2,TOPIC_TAG_N")
    print("\nFor starting monitors:")
    print("\t rosrun sentor sentor_client.py start TOPIC_TAG_1,TOPIC_TAG_2,TOPIC_TAG_N")
    print("\nFor killing monitors:")
    print("\t rosrun sentor sentor_client.py kill TOPIC_TAG_1,TOPIC_TAG_2,TOPIC_TAG_N")
    print("\nTopic tags are optional args used to load/stop/start/kill specific monitors")
    print("\n\n")
    
    
def sentor_client(name, config, tags):
    
    rospy.wait_for_service(name, timeout=5.0)
    try:
        s = rospy.ServiceProxy(name, Client)
        req = ClientRequest()
        req.config = config
        req.topic_tags = tags
        resp = s.call(req)
        rospy.loginfo(resp)
    except rospy.ServiceException as e:
        print("Service call failed: {}".format(e))
###################################################################################################################
    
    
###################################################################################################################
if __name__ == "__main__":

    modes = {}
    modes["load"] = "/sentor/load_monitors"
    modes["stop"] = "/sentor/stop_monitors"
    modes["start"] = "/sentor/start_monitors"
    modes["kill"] = "/sentor/kill_monitors"

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", type=str,
                        help="(str) load, stop, start or kill. Required.")
    parser.add_argument("--config", type=str, default="",
                        help="(str) sentor config file. Required if mode=load.")
    parser.add_argument("--tags", type=str, default="",
                        help="(str) topic tags used to load/stop/start/kill individual monitors. Optional.")
    parser.add_argument("--spin", type=lambda x: (str(x).lower() == "true"), default=False, 
                        help="(bool) Spin the client and kill loaded monitors on shutdown. Default=False")
    

    rospy.init_node("sentor_client", anonymous=True)

    args = parser.parse_args()
    if args.mode == "load" and args.config is None:
        rospy.logerr("--config CONFIG  (str) sentor config file. Required if mode=load.")
        sys.exit(1)

    sentor_client(modes[args.mode], args.config, args.tags)





       # if '-h' in sys.argv or '--help' in sys.argv or len(sys.argv) < 2:
    #     usage()
    #     sys.exit(1)
    # else:
    #     mode = ""
    #     config = ""
    #     tags = ""
    #     if sys.argv[1] == "load":
    #         mode = "/sentor/load_monitors"
    #         if len(sys.argv) > 2:
    #             config = sys.argv[2]
    #             if len(sys.argv) > 3:
    #                 tags = sys.argv[3]
    #         else:
    #             usage()
    #             sys.exit(1)
    #     elif sys.argv[1] == "stop":
    #         mode = "/sentor/stop_monitors"
    #         if len(sys.argv) > 2:
    #             tags = sys.argv[2]
    #     elif sys.argv[1] == "start":
    #         mode = "/sentor/start_monitors"
    #         if len(sys.argv) > 2:
    #             tags = sys.argv[2]
    #     elif sys.argv[1] == "kill":
    #         mode = "/sentor/kill_monitors"
    #         if len(sys.argv) > 2:
    #             tags = sys.argv[2]
    #     else:
    #         usage()
    #         sys.exit(1)
###################################################################################################################