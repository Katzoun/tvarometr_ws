# Tvarometr - Automated Face Analysis and Robot Drawing System

An automated system for capturing, analyzing, and robotically rendering human
faces at public events. Computer vision and neural networks detect a face and
predict age, gender and emotion; the result becomes a trajectory that an ABB
GoFa robot draws over the RWS 2.0 interface.

Built for events such as open days at Brno University of Technology, Faculty of
Mechanical Engineering.

> Being rebuilt on branch `rebuild-docker-bt` towards a fully Dockerized system
> with a BehaviorTree.CPP orchestrator. Development containers are the only
> supported mode right now - there is no production image.

**Česky: [rychlý start pro vývoj](VYVOJ.md).**

## Workflow

1. Webcam captures an image of a person
2. Neural networks analyze face attributes (age, gender, emotion)
3. The system generates a drawing trajectory from the analysis
4. The trajectory goes to the ABB GoFa over RWS 2.0
5. The robot draws

## Architecture

### ROS2 packages

#### `tvarometr_inference`
Image acquisition and neural network inference.

- **Nodes:** `usb_cam` (from the `usb_cam` package) streams the webcam,
  configured in `config/usb_cam.yaml`; `inference_node_exec` keeps the newest
  frame and runs the models over it; `drawing_node_exec` turns a face analysis
  into the path to draw. Both are managed nodes, and the launch file starts
  only the first one.
- **Topics:** `/image_raw` (sensor_msgs/Image), the camera stream.
- **Actions:** `inference_node/run_inference` answers with a `FaceAttributes` -
  age, gender, emotion and where the face sat in the frame;
  `drawing_node/generate_drawing` turns that into a `PoseArray` to draw.
  Labels are the models' own English ones; the Czech wording is decided in the
  drawing node.

#### `robot_control`, `robot_control_msgs`
The ABB robot driver and its interface definitions. They live in their own
repository, [abb_rws2_ros2_driver](https://github.com/Katzoun/abb_rws2_ros2_driver),
with their own containers, and are not built here. Its README documents the
nodes, the motion actions and the request service.

#### `tvarometr_orchestrator`
The BehaviorTree.CPP tree that drives a run: ask the camera for a face, turn the
analysis into a path, hand the path to the robot. C++, because that is what
BT.CPP is - version 4, the one Groot2 speaks to.

Only a skeleton so far. It loads `behavior_trees/tvarometr.xml`, ticks it once
and exits; the tree holds a single log line. The nodes that call the three
actions arrive one at a time.

#### `master_pkg` (reference only)
The pre-rebuild system: state machine, its own RWS client, path generation and
the turtlesim preview. Not built into any container - it is kept as the
reference for reimplementing the orchestrator and no longer runs as part of the
stack.

### Neural network models

Kept in `models/` at the repo root, out of the source tree - they are half a
gigabyte between them, stored via Git LFS. The inference node takes a
`models_dir` parameter, `/opt/tvarometr/models` inside the container.

- `yolov8x_person_face.pt` - face detection (YOLOv8)
- `model_imdb_cross_person_4.22_99.46.pth.tar` - age estimation
- `affectnet7_model.pth` - emotion classification

### Python libraries

Pinned in `docker/requirements-vision.txt`. A few of those pins are
load-bearing - the file explains which and why.

## Getting started

### Requirements

- Ubuntu 22.04 with a native Docker Engine. Not Docker Desktop: it runs
  containers in a VM and cannot pass the host GPU through on Linux. Check that
  `docker context ls` shows `default` as active.
- NVIDIA Container Toolkit and an NVIDIA GPU.
- Git LFS on the host (`apt install git-lfs`), for the model weights.
- vcstool on the host (`apt install python3-vcstool`), to fetch the driver.
- An ABB GoFa with RWS 2.0, to drive a real robot.

ROS2 Humble, Python and every model dependency live in the container, so
nothing beyond the list above is needed on the host.

### First run

```bash
git clone https://github.com/Katzoun/tvarometr_ws.git
cd tvarometr_ws
git lfs install && git lfs pull      # weights; LFS pointers are ~130 bytes
vcs import src < dependencies.repos        # the ABB driver, from its own repository
docker compose -f docker-compose.dev.yml up -d --build
```

The order matters. The orchestrator is C++ and needs the driver's
`robot_control_msgs` headers to build, so its image resolves that package's
manifest - `vcs import` has to have run first or the build fails on a missing
file. `dependencies.repos` pins the repository and branch; the import lands in
`src/abb_rws2_ros2_driver/` and is git-ignored here, so the driver stays
versioned in its own repo, not this one. `vcs pull src` updates it later.

`docker-compose.dev.yml` is the only compose file here. It defines three
environments over the one source tree:

| Service | Needs | Owns | Started by |
| --- | --- | --- | --- |
| `orchestrator` | CPU only | `tvarometr_orchestrator` | `up -d` |
| `vision` | NVIDIA GPU | `tvarometr_interfaces`, `tvarometr_inference` | `--profile vision` |
| `driver` | a robot | nothing - it runs the driver's own image | `--profile robot` |

The orchestrator is the one that runs anywhere, so it comes up by default; the
other two sit behind profiles and start when you name their profile or the
service. The first two bind-mount the repo at `/workspace` and then idle - they
never launch a node by themselves, so you start one from a terminal and stop it
with Ctrl+C.

#### The robot driver

The driver is a separate project:
[abb_rws2_ros2_driver](https://github.com/Katzoun/abb_rws2_ros2_driver). It is
not developed here - the `driver` service builds its production image with the
driver's own Dockerfile and runs it, so this repo never describes the driver's
dependencies. To work on the driver itself, open its repository, which carries
its own dev container.

```bash
docker compose -f docker-compose.dev.yml --profile robot up -d
```

Set the robot's address and credentials as the driver's README describes before
the first run. Its own `docker-compose.prod.yml` declares the same image and
container name, so run the driver from one place or the other, not both.

### VS Code

Open the repo on the host, run **Dev Containers: Reopen in Container** and pick
**orchestrator** or **vision**. That service starts, its packages build
automatically, and every terminal in the window runs inside the container. To
work on both at once, open the repo in a second window and pick the other one;
closing a window leaves the containers running. See the
[VS Code multi-container workflow](https://code.visualstudio.com/remote/advancedcontainers/connect-multiple-containers).

There is no dev container for the driver here, on purpose - it has one in its
own repository.

### Command line

```bash
docker compose -f docker-compose.dev.yml exec orchestrator bash   # or: exec vision bash
```

Every shell sources ROS through `docker/ros-env.sh`. Build once after the
container is created:

```bash
# in orchestrator
colcon build --symlink-install --packages-select \
    robot_control_msgs tvarometr_interfaces tvarometr_orchestrator
# in vision
colcon build --symlink-install --packages-select tvarometr_interfaces tvarometr_inference

source /opt/colcon_ws/install/setup.bash
```

Stop everything from the host:

```bash
docker compose -f docker-compose.dev.yml --profile vision --profile robot stop
```

## Running the system

### Robot driver

From the driver's own container:

```bash
ros2 launch robot_control robot_control.launch.py
```

It is a managed node and comes up `unconfigured`, doing nothing until it is
driven through the lifecycle from a second terminal:

```bash
ros2 lifecycle set /robot_controller configure
ros2 lifecycle set /robot_controller activate
```

**The orchestrator does not drive it yet.** Its tree is still a skeleton, so
goals go by hand for now. The request service and the motion actions are
documented in the
[driver's README](https://github.com/Katzoun/abb_rws2_ros2_driver).

### Orchestrator

In an orchestrator terminal:

```bash
ros2 launch tvarometr_orchestrator orchestrator.launch.py
```

The tree runs once and the process exits with it, so this is not something you
leave running - you start it when there is a face to draw. Point it at another
tree with `tree_file:=/workspace/path/to.xml`.

### Vision

In a vision terminal:

```bash
ros2 launch tvarometr_inference vision.launch.py device:=cuda:0 use_camera:=false
```

The node comes up `unconfigured` and holds no weights. Configure loads them,
which takes a while; activate lets it accept goals:

```bash
ros2 lifecycle set /inference_node configure
ros2 lifecycle set /inference_node activate
```

Then run the models over the newest frame:

```bash
ros2 action send_goal /inference_node/run_inference \
    tvarometr_interfaces/action/RunInference {}
```

To use a webcam, set `CAMERA_DEVICE` in `.env` before creating the container and
launch with `use_camera:=true`. Models are mounted read-only from `models/`, so
swapping weights needs only a node restart, not an image rebuild.

Quick GPU check:

```bash
python3 -c 'import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))'
```

## Working on the code

Python edits take effect when you restart the node - `--symlink-install` makes
the installed package point back at the source. Rebuild only after changing
message or action definitions, entry points, or installed launch and config
files. When `tvarometr_interfaces` changes, rebuild every consumer.

Every container uses host networking, shared IPC and the same `ROS_DOMAIN_ID`,
so nodes in any of them discover each other.

### Where the files are

Colcon writes outside the bind mount, so build output never lands on the host:

```text
/workspace/src/          source, shared with the host
/opt/colcon_ws/build/    inside the container
/opt/colcon_ws/install/  inside the container
/opt/colcon_ws/log/      inside the container
```

The paths come from the container's `docker/colcon-defaults-*.yaml`, which also
pins which packages it builds - the source tree holds every package, but each
container only has the dependencies for its own, so a bare `colcon build` there
builds its own and nothing else. They are not in a volume:
build output survives stopping and starting a container and is discarded when
the container is rebuilt, so every rebuild starts from a clean install. Named
volumes cover only editor extensions and assistant settings, which are
expensive to reinstall.

### Rebuilding an image

After a change to a requirements file or a Dockerfile, use **Dev Containers:
Rebuild Container**, or on the host:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

### Which file does what

| File | Role |
| --- | --- |
| `docker/orchestrator.Dockerfile`, `docker/vision.Dockerfile` | Dependencies for each container. No source, models or prebuilt workspace. |
| `docker-compose.dev.yml` | How the containers run: mounts, GPU, camera, network, profiles. |
| `.devcontainer/orchestrator/`, `.devcontainer/vision/` | Which service VS Code attaches to, its extensions, and the build on create. |
| `dependencies.repos` | The driver's repository and branch, for `vcs import`. |
| `docker/colcon-defaults-*.yaml` | Colcon output paths, and which packages each container builds. |
| `docker/ros-env.sh` | Sources ROS and the built workspace in every shell. |
| `docker/entrypoint.sh` | Sources ROS, then runs the container command. |

## Configuration

### Robot

Address and credentials belong to the driver and are documented in its
[README](https://github.com/Katzoun/abb_rws2_ros2_driver). The virtual
controller usually listens on port 80, the physical one on 443.

### Environment

Optional `.env` in the repo root, read by Compose:

| Variable | Default | Effect |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `42` | DDS domain; set the same one for the driver |
| `CAMERA_DEVICE` | `/dev/null` | Host webcam passed to vision as `/dev/video0` |

## Project structure

```
tvarometr_ws/
├── src/
│   ├── tvarometr_inference/       # Camera + the three networks (GPU container)
│   │   ├── launch/vision.launch.py
│   │   ├── config/usb_cam.yaml    # resolution, framerate, device path
│   │   └── tvarometr_inference/
│   │       ├── inference_node.py
│   │       ├── drawing_node.py    # face analysis -> the path to draw
│   │       └── vendor/            # MiVOLO and ResEmoteNet, vendored as-is
│   ├── tvarometr_interfaces/      # msg/srv/action definitions
│   ├── tvarometr_orchestrator/    # BehaviorTree.CPP orchestrator (C++)
│   │   ├── src/orchestrator_node.cpp
│   │   └── behavior_trees/        # the trees themselves, as XML
│   ├── abb_rws2_ros2_driver/      # ABB driver, imported by vcstool, git-ignored
│   └── master_pkg/                # Pre-rebuild system, reference only
│       ├── launch/control.launch.py
│       └── master_pkg/
│           ├── master.py
│           └── utils/
│               ├── state_machine.py
│               ├── rwsprovider.py
│               ├── rwswrappers.py
│               └── path_generator_multiline.py
├── models/                        # Network weights, Git LFS
├── docker/                        # Dockerfile, pinned requirements, entrypoint
├── .devcontainer/                 # VS Code configs for orchestrator/ and vision/
├── dependencies.repos                   # where the ABB driver is imported from
└── docker-compose.dev.yml         # orchestrator + optional vision and driver
```

## The pre-rebuild system

`master_pkg` drove the whole pipeline before the rebuild. Its state machine ran
IDLE → CAPTURE → INFERENCE → TRAJECTORY_GENERATION → ROBOT_EXECUTION → COMPLETE,
with a multi-line trajectory generator turning face analysis into a drawable
path. It is reference material for the BehaviorTree orchestrator, not part of
any container.

Running it needs a host ROS2 install, including `ros-humble-usb-cam`:

```bash
git lfs install && git lfs pull
colcon build
source install/setup.bash

ros2 launch tvarometr_inference vision.launch.py \
    device:=cuda:0 models_dir:=$PWD/models     # terminal 1
ros2 launch master_pkg control.launch.py       # terminal 2
ros2 run master_pkg keyboard_publisher_exec    # terminal 3
```

## Institution

Developed at Brno University of Technology (BUT)  
Faculty of Mechanical Engineering (FME)  
Brno, Czech Republic
