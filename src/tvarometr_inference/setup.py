import os
from glob import glob

from setuptools import find_packages, setup

package_name = "tvarometr_inference"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Tomas Janousek",
    maintainer_email="tomas.janousek02@gmail.com",
    description="Face detection with age, gender and emotion estimation",
    license="MIT",
    extras_require={"test": ["pytest"]},
    entry_points={
        "console_scripts": [
            "camera_node_exec = tvarometr_inference.camera_node:main",
            "inference_node_exec = tvarometr_inference.inference_node:main",
        ]
    },
)
