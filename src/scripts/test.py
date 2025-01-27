#!/usr/bin/env python
"""
Created on Wed Dec  4 17:35:05 2019

@author: Adam Binch (abinch@sagarobotics.com)
"""
#####################################################################################
import rospy
from std_msgs.msg import Bool
from std_srvs.srv import SetBool, SetBoolResponse


class Tester(object):
    
    
    def __init__(self):

        self.pub_expr_1 = True
        self.pub_expr_2 = True
        
        self.expr_1 = True
        self.expr_2 = True

        rospy.Service('/pub_expr_1', SetBool, self.func_pub_expr_1)
        rospy.Service('/pub_expr_2', SetBool, self.func_pub_expr_2)
        
        rospy.Service('/set_expr_1', SetBool, self.set_expr_1)
        rospy.Service('/set_expr_2', SetBool, self.set_expr_2)
        
        self.pub_1 = rospy.Publisher("/expr_1", Bool, queue_size=10)
        self.pub_2 = rospy.Publisher("/expr_2", Bool, queue_size=10)
        
        self.rate = rospy.Rate(10) 
        
        
    def func_pub_expr_1(self, req):
        
        self.pub_expr_1 = req.data        
        
        ans = SetBoolResponse()
        ans.success = True
        ans.message = "Publishing expr_1 = {}".format(req.data)
        
        return ans


    def func_pub_expr_2(self, req):
        
        self.pub_expr_2 = req.data        
        
        ans = SetBoolResponse()
        ans.success = True
        ans.message = "Publishing expr_2 = {}".format(req.data)
        
        return ans
        
        
    def set_expr_1(self, req):
        
        self.expr_1 = req.data        
        
        ans = SetBoolResponse()
        ans.success = True
        ans.message = "Set expr_1 = {}".format(req.data)
        
        return ans


    def set_expr_2(self, req):
        
        self.expr_2 = req.data        
        
        ans = SetBoolResponse()
        ans.success = True
        ans.message = "Set expr_2 = {}".format(req.data)
        
        return ans
        
        
    def run(self):
        
        while not rospy.is_shutdown():
            
            if self.pub_expr_1:
                self.pub_1.publish(Bool(self.expr_1))  
                
            if self.pub_expr_2:
                self.pub_2.publish(Bool(self.expr_2))   
            
            self.rate.sleep()
#####################################################################################


##################################################################################### 
if __name__ == "__main__":

    rospy.init_node("tester")
    
    tester = Tester()
    tester.run()
#####################################################################################
