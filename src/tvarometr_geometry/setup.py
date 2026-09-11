from setuptools import find_packages, setup

package_name = 'tvarometr_geometry'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    package_data={package_name: ['fonts/*.svg', 'fonts/*.txt']},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'svg.path==7.0'],
    zip_safe=True,
    maintainer='Tomas Janousek',
    maintainer_email='tomas.janousek02@gmail.com',
    description='Turning what the camera found into coordinates the robot can go to',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'generate_text_path = tvarometr_geometry.path_generator:main',
            'trajectory_svg = tvarometr_geometry.trajectory_svg:main',
            'centring_node_exec = tvarometr_geometry.centring_node:main',
            'drawing_node_exec = tvarometr_geometry.drawing_node:main',
        ],
    },
)
