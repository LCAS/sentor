#!/usr/bin/env python3
"""
CustomLambdaExample.py

This module defines a custom lambda function for SENTOR monitoring in ROS2.

Created on Fri Nov 20 11:35:22 2020
@author: Adam Binch (abinch@sagarobotics.com)
Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang

Example in yaml:

signal_lambdas:
  - expression: "CustomLambda"
    file: "CustomLambdaExample"
    package: "sentor"
    safety_critical: False
    process_indices: [<indices>]
    repeat_exec: False
    tags: ["navigation"]
    when_published: False

"""

def CustomLambda(msg):
    """
    Custom lambda that returns True if msg.data equals "t1-r1-c2".
    
    Args:
        msg: A ROS message (expected to have a 'data' attribute)
        
    Returns:
        bool: True if msg.data equals "t1-r1-c2", False otherwise.
    """
    return msg.data == "t1-r1-c2"


if __name__ == '__main__':
    # Test the custom lambda function with a dummy message
    class DummyMsg:
        def __init__(self, data):
            self.data = data

    test_msg1 = DummyMsg("t1-r1-c2")
    test_msg2 = DummyMsg("other")
    
    print("CustomLambda(test_msg1):", CustomLambda(test_msg1))  # Expected: True
    print("CustomLambda(test_msg2):", CustomLambda(test_msg2))  # Expected: False