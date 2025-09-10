from setuptools import setup, find_packages

package_name = 'sentor'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@example.com',
    description='Python-based Sentor monitoring system',
    license='MIT',
    entry_points={
        'console_scripts': [
            'sentor_node = sentor.sentor_node:main',
            'test_sentor = sentor.test_sentor:main',
        ],
    },
)
