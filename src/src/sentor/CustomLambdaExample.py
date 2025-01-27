#!/usr/bin/env python
"""
Created on Fri Nov 20 11:35:22 2020

@author: Adam Binch (abinch@sagarobotics.com)
"""
#########################################################################################################
# SENTOR CUSTOM LAMBDA

def CustomLambda(msg):
    return msg.data == "t1-r1-c2"
#########################################################################################################