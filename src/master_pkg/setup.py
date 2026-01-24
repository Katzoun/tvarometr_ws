from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'master_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Include launch files
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='robolab',
    maintainer_email='robolab@todo.todo',
    description='TODO: Package description',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'master_node_exec = master_pkg.master:main',
            'keyboard_publisher_exec = master_pkg.keyboard_publisher:main',
            'turtle_drawer_exec = master_pkg.turtle_simulator:main',
        ],
    },
)
