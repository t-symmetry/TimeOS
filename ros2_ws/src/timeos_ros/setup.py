from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'timeos_ros'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Include launch files
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*.launch.py'))),
        # Include config files
        (os.path.join('share', package_name, 'config'),
            glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='TimeOS Contributors',
    maintainer_email='T-Symmetry@skylarkSoftware.me',
    description='ROS2 nodes for TimeOS temporal research platform',
    license='Proprietary',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # Core nodes
            'timeline_node = timeos_ros.nodes.timeline_node:main',
            'field_generator_node = timeos_ros.nodes.field_generator_node:main',
            'tdu_node = timeos_ros.nodes.tdu_node:main',
            'causality_monitor_node = timeos_ros.nodes.causality_monitor_node:main',
            'safety_monitor_node = timeos_ros.nodes.safety_monitor_node:main',
            'thermal_monitor_node = timeos_ros.nodes.thermal_monitor_node:main',
            'anchor_node = timeos_ros.nodes.anchor_node:main',
            # Research nodes
            'experiment_controller_node = timeos_ros.nodes.experiment_controller_node:main',
            't_symmetry_analyzer_node = timeos_ros.nodes.t_symmetry_analyzer_node:main',
            'sensor_aggregator_node = timeos_ros.nodes.sensor_aggregator_node:main',
            'data_recorder_node = timeos_ros.nodes.data_recorder_node:main',
        ],
    },
)
