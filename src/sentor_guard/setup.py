from setuptools import setup

package_name = 'sentor_guard'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@example.com',
    description='Safety guard libraries and nodes for sentor-based autonomous systems',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'python_guard_example = examples.python_guard_example:main',
        ],
    },
)
