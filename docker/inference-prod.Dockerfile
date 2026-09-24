# Inference for a run: the dev image's dependencies with the source and the
# weights built in instead of mounted.

FROM tvarometr/inference:dev

COPY src/tvarometr_interfaces /workspace/src/tvarometr_interfaces
COPY src/tvarometr_inference /workspace/src/tvarometr_inference

# Only the three inference.yaml loads. The other two files in models/ belong to
# the benchmark and would add 600 MB. .dockerignore lets these through.
COPY models/yolov8x_person_face.pt /opt/tvarometr/models/
COPY models/model_imdb_cross_person_4.22_99.46.pth.tar /opt/tvarometr/models/
COPY models/enet_b2_7.pt /opt/tvarometr/models/

RUN . /opt/ros/${ROS_DISTRO}/setup.sh && colcon build

CMD ["ros2", "launch", "tvarometr_inference", "inference.launch.py"]
