from setuptools import setup
from glob import glob
import os

package_name = 'robot_state_machine'
pkg = package_name

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', [f'resource/{pkg}']),
        (f'share/{pkg}', ['package.xml']),
    ],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='bob',
    maintainer_email='bob@live.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    entry_points={
        'console_scripts': [
            'sentor = robot_state_machine.sentor:main', #new SENTOR node for testing
            'bridge_to_arduino = robot_state_machine.bridge_to_arduino:main', # Communication with Arduino
            'robot_state_machine = robot_state_machine.robot_state_machine:main', #new Robot State Machine for testing
            'directions = robot_state_machine.direction:main',  # Direction command publisher
            'state_mode_selectors = robot_state_machine.state_mode_selectors:main ',  # Main communication node  
            'robot_state_machine_sentor = robot_state_machine.robot_state_machine_sentor:main', #new Robot State Machine for testing using sentor topics
            'joy_robot_state_machine = robot_state_machine.joy_robot_state_machine:main', # Joystick to Robot State Machine bridge
        ],
    },
)
