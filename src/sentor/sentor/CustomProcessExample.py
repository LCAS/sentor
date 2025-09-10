#!/usr/bin/env python3
"""
CustomProcessExample.py

This module defines a custom process class for SENTOR in ROS2.
The custom process prints a message during initialization and when executed.

Created on Mon Nov 23 16:26:27 2020
@author: Adam Binch (abinch@sagarobotics.com)
Converted from ROS1 to ROS2 2025
@author: Zhuoling Huang

Example in yaml:
execute:
  - custom:
      verbose: True
      name: "CustomProcess"
      file: "CustomProcessExample"
      package: "sentor"
      init_args: 
        - "Custom process initialisation message"
      run_args: 
        - "Custom process runtime message"

"""

class CustomProcess:
    def __init__(self, message):
        """
        Initialization of the custom process.
        
        Args:
            message (str): A message to print during initialization.
        """
        print("CustomProcess initialized with message:", message)
    
    def run(self, message):
        """
        Executes the custom process when the condition is met.
        
        Args:
            message (str): A message provided at runtime.
        """
        print("CustomProcess running with message:", message)

if __name__ == '__main__':
    # Test the custom process if this file is run standalone.
    cp = CustomProcess("Initialization test")
    cp.run("Runtime test")
