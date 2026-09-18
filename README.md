# Tvarometr - Automated Face Analysis and Robot Drawing System

An ABB GoFa photographs a visitor, neural networks estimate their age, gender and
emotion, and the robot writes the result on a whiteboard, then wipes it. Built for
open days at Brno University of Technology, Faculty of Mechanical Engineering.

> Being rebuilt on branch `rebuild-docker-bt` with Docker and a BehaviorTree.CPP
> orchestrator. Development containers are the only supported mode for now.

**Česky: [rychlý start pro vývoj](VYVOJ.md).**

## How a run goes

The operator starts each run from the keyboard:

1. Drive to the photo pose.
2. Centre the visitor's face in the camera.
3. Estimate age, gender and emotion over several frames.
4. Generate the label, value and wipe paths.
5. Write the labels (first run only), then the values, and back off.
6. Wait for the operator, wipe the values and back off.

Every step runs for real; what still needs tuning is in [Roadmap](#roadmap).

## Architecture

| Node | Package | Container |
| --- | --- | --- |
| `orchestrator` - the behaviour tree | `tvarometr_orchestrator` | orchestrator |
| `trajectory_node`, `centring_node` | `tvarometr_geometry` | orchestrator |
| `camera`, `inference_node` | `tvarometr_inference` | inference (GPU) |
| `robot_controller` | `robot_control` (separate repo) | driver |

### `tvarometr_orchestrator`

The BehaviorTree.CPP 4 tree `behavior_trees/tvarometr.xml` drives everything. C++,
one BT node per header/source pair.

- **Bring-up.** Configures and activates the driver and the inference node unless
  already active, so a restart keeps the robot session and the weights.
- **Each run** checks both are active, makes the robot ready (mastership, motors,
  RAPID), and goes through the steps above. `board_written` remembers whether the
  labels are up until the process restarts.
- **Keys.** `S` starts a run, `C` continues (wipe, or retry a failed scan), `E`
  aborts back to waiting, and `S`/`C` stay refused until `Q` acknowledges it. An
  abort cancels the motion, but the driver runs out its queue - it is no e-stop.
- **Retry.** If framing or analysis fails, the robot returns to the photo pose and
  waits: `C` tries again, `E` gives up.
- **Groot2** attaches on port 1667 (`groot2_port`).

### `tvarometr_geometry`

Python, plain nodes (nothing to load).

- **`trajectory_node_exec`** serves `trajectory_node/generate_trajectories`: label,
  value and wipe `PoseArray`s in metres, with the Czech wording. See `TRAJECTORIES.md`.
- **`centring_node_exec`** serves `centring_node/centre_face`: ask `detect_face`,
  move the camera in Z, ask again. Steps are measured from the goal's `photo_pose`,
  never the robot's reported position, and Z stays in `[min_z, max_z]`.
  - A face is about `face_height_m` tall, which turns pixels into metres; a step
    corrects `gain` of the error, up to `max_step`.
  - With no face in view it steps blindly towards the top of the visitor's body
    box. With nobody in view at all it sweeps in `search_step` steps, down first
    and up after the lower limit. A turned-away head is waited out.
  - Success when the face is within `tolerance` of `target_y`, or at a Z limit with
    the face in view (`at_limit`). Failure at a limit without a face, out of steps
    or time, or after `max_lost_detections` useless answers.
  - Settings in `config/centring.yaml`; `dry_run` logs moves without sending them.

### `tvarometr_inference`

- **`camera_node_exec`** publishes the webcam's own JPEGs on `/image_raw/compressed`,
  undecoded. `camera.launch.py` sets the V4L2 controls first. It replaces usb_cam,
  whose raw MJPEG mode segfaults in 0.8.1.
- **`inference_node_exec`** is managed: configure loads the weights, activate starts
  one thread that runs YOLOv8 on every new frame. Only that thread touches the
  models, so requests never hold up the preview.
  - `run_inference` (action) collects the visitor's face from `samples` frames and
    answers with the median age and the averaged gender and emotion probabilities.
    Fewer than `min_samples` by `sample_timeout_s` fails.
  - `detect_face` (service) answers from the latest frame taken after `not_before`:
    where the visitor stands and where their face is.
  - The **visitor** is the one with the tallest face near `axis_x`, the line over
    the floor mark; `axis_falloff` away counts half, a face shorter than
    `min_face_height_px` not at all. Face height, because it says how far somebody
    stands whatever their size, while a child close up is as wide as an adult far
    away. While no face is that tall, the widest body over `min_person_width_px`
    wins instead. No memory between frames.
  - `scene_image/compressed` (for the TV) shows plain boxes, the visitor green;
    `debug_image/compressed` adds every number the rules decide on - body width,
    face height, axis weight, which rule won and its thresholds - plus attributes
    and the axis. Both are JPEG, sent only while watched.

Weights are in `models/` (Git LFS), mounted at `/opt/tvarometr/models`:
`yolov8x_person_face.pt` (detection), `model_imdb_cross_person_4.22_99.46.pth.tar`
(age, gender), `enet_b2_7.pt` (emotion, HSEmotion; chosen in `benchmark/`).

### `tvarometr_interfaces`

`FaceAttributes`, `RunInference` and `CentreFace` actions, `DetectFace` and
`GenerateTrajectories` services.

### Robot driver

[abb_rws2_ros2_driver](https://github.com/Katzoun/abb_rws2_ros2_driver), imported
with vcstool: a managed node with `robot_robtarget_move`, `robot_jointtarget_move`
and `controller_request`, documented in its README. This repo only builds and runs
its production image.

## Getting started

### Requirements

- Ubuntu 22.04 with native Docker Engine (not Docker Desktop, which cannot pass the GPU).
- NVIDIA GPU and NVIDIA Container Toolkit, for the inference container.
- Git LFS and vcstool (`apt install git-lfs python3-vcstool`).
- An ABB GoFa with RWS 2.0, or RobotStudio's virtual controller.

### First run

On the host, before any image build:

```bash
git clone https://github.com/Katzoun/tvarometr_ws.git
cd tvarometr_ws
git lfs install && git lfs pull       # weights; without LFS you get 130-byte pointers
vcs import src < dependencies.repos   # the robot driver and behaviortree_ros2
```

Both imports are git-ignored; `vcs pull src` updates them. The inference container
needs a webcam at `/dev/video0`; see [Environment](#environment) otherwise.

### Containers

| Service | Needs | Builds | Profile |
| --- | --- | --- | --- |
| `orchestrator` | CPU only | `tvarometr_orchestrator`, `tvarometr_geometry`, `tvarometr_interfaces` | none |
| `inference` | NVIDIA GPU | `tvarometr_inference`, `tvarometr_interfaces` | `inference` |
| `driver` | a robot | the driver's production image | `robot` |

`orchestrator` and `inference` mount the repo at `/workspace` and idle; `driver`
starts by itself. **From the host, always name the service** - a bare `up -d
--build` recreates the orchestrator and kills an attached VS Code window.

**VS Code:** *Dev Containers: Reopen in Container*, pick one service; use a second
window for the other. It will not attach to a container created with `compose up`
(`rmdir: Directory not empty`) - remove it first with
`docker compose -f docker-compose.dev.yml rm -sf orchestrator`.

**Command line:**

```bash
docker compose -f docker-compose.dev.yml up -d --build orchestrator   # --profile inference for inference
docker compose -f docker-compose.dev.yml exec orchestrator bash
MAKEFLAGS=-j2 colcon build --parallel-workers 1 --symlink-install
```

Cap C++ builds like this: unbounded, the orchestrator build runs a 16 GB machine
out of memory. Shells source the workspace through `docker/ros-env.sh`; in one open
during a build, `source /opt/colcon_ws/install/setup.bash`.

## Running the system

In this order; all containers share the host network and `ROS_DOMAIN_ID`.

### 1. Robot driver - host

```bash
docker compose -f docker-compose.dev.yml --profile robot up -d --build --no-deps driver
docker logs -f abb_rws2_ros2_driver
```

The tree activates it. Its `robot_control.yaml` is baked into the image, so rerun
the command after editing it. RAPID is maintained by hand, not from this repo.

### 2. Geometry nodes - orchestrator container

```bash
ros2 run tvarometr_geometry trajectory_node_exec
ros2 launch tvarometr_geometry centring.launch.py  # config:=... for another YAML
```

### 3. Inference - inference container

```bash
ros2 launch tvarometr_inference inference.launch.py   # use_camera:=false without a webcam
ros2 launch tvarometr_inference camera.launch.py      # or the camera alone, for tuning it
ros2 run rqt_image_view rqt_image_view /inference_node/debug_image/compressed
ros2 run rqt_image_view rqt_image_view /inference_node/scene_image/compressed
```

GUI tools need `xhost +SI:localuser:root` on the host; the inference dev container
runs it on start, after a new login run it yourself. Without the tree:

```bash
ros2 lifecycle set /inference_node configure        # loads the weights, takes a while
ros2 lifecycle set /inference_node activate
ros2 topic hz /image_raw/compressed
ros2 action send_goal -f /inference_node/run_inference tvarometr_interfaces/action/RunInference {}
```

GPU check: `python3 -c 'import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))'`.

### 4. Orchestrator - orchestrator container

```bash
ros2 run tvarometr_orchestrator orchestrator_node
```

`ros2 run`, because launch does not pass the keyboard through. Another tree:
`--ros-args -p tree_file:=/workspace/path/to.xml`. It exits if the driver or the
inference node cannot be brought up, so start inference first.

## Working on the code

- **Python, tree XML** - installed by symlink; restart the node. Rebuild after
  adding entry points, launch or config files.
- **C++** - rebuild after every change.
- **Interfaces** - rebuild them and their users, in both containers.
- **Dockerfile, requirements** - *Dev Containers: Rebuild Container*.

Colcon writes to `/opt/colcon_ws` inside the container, gone after a rebuild;
`docker/colcon-defaults-*.yaml` sets the paths and packages. Tests: `colcon test
--packages-select tvarometr_geometry` or `tvarometr_inference`, then
`colcon test-result --verbose`.

| File | Role |
| --- | --- |
| `docker/*.Dockerfile` | Dependencies only - no source, models or build. |
| `docker/requirements-*.txt` | Python pins. |
| `docker-compose.dev.yml` | Mounts, GPU, camera, network, profiles. |
| `.devcontainer/*/` | Which service VS Code attaches to, build on create. |
| `dependencies.repos` | Driver and behaviortree_ros2, for `vcs import`. |
| `docker/colcon-defaults-*.yaml` | Colcon paths and packages per container. |
| `docker/ros-env.sh`, `docker/entrypoint.sh` | Source ROS in every shell. |

## Configuration

**Robot.** Address and credentials in the driver's `robot_control.yaml`; the
virtual controller listens on port 80, the physical one on 443.

**Tree.** `tvarometr.xml` holds the photo and back-off poses (`x,y,z,qx,qy,qz,qw`,
metres), speeds and `tool`/`wobj` names, which must exist on the controller. Empty
`wobj` is `wobj0`; RAPID writes quaternions as `[qw,qx,qy,qz]`.

**Inference** (`tvarometr_inference/config/`, restart the launch after editing):

- `inference.yaml` - device, weights, topic, visitor selection, averaging, JPEG
  quality. Line the axis up live: `ros2 param set /inference_node axis_x 0.45`.
- `camera.yaml` - device, resolution, framerate from
  `v4l2-ctl -d /dev/video0 --list-formats-ext`. The GPU analyses about 20 fps anyway.
- `camera_controls.yaml` - exposure, focus, white balance, by the names
  `v4l2-ctl -d /dev/video0 --list-ctrls-menus` shows.

**Trajectories.** `trajectory_node` parameters (letter size, value column, eraser
width, pen orientation) via `--ros-args -p name:=value`.

### Environment

From the host shell or an optional `.env`. The camera is mapped at container
creation, so rebuild inference after changing it.

| Variable | Default | Effect |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `42` | DDS domain for all three containers |
| `CAMERA_DEVICE` | `/dev/video0` | Host webcam for inference; `/dev/null` without one |

## Roadmap

1. **Runs with real people** - Z limits, `gain` and `min_person_width_px` tuned on
   visitors of different heights.
2. **Emotion** - a better model or checkpoint, chosen on labelled photos.
3. **One launch per container** for the event.

Known gaps: an abort while drawing leaves a dirty board; the eraser has no tooldata
of its own; the driver's RWS timeout can be too short for `make_robot_ready`.

## Project structure

```
tvarometr_ws/
├── src/
│   ├── tvarometr_orchestrator/     # behaviour tree (C++)
│   │   ├── behavior_trees/tvarometr.xml
│   │   └── include/, src/          # one BT node per pair; orchestrator_node.cpp is main
│   ├── tvarometr_geometry/         # trajectory and centring nodes (Python)
│   ├── tvarometr_inference/        # camera and the networks (Python, GPU)
│   │   ├── config/                 # inference.yaml, camera.yaml, camera_controls.yaml
│   │   └── tvarometr_inference/vendor/   # MiVOLO and ResEmoteNet, as-is
│   ├── tvarometr_interfaces/       # msg, srv, action
│   ├── abb_rws2_ros2_driver/       # imported by vcstool, git-ignored
│   └── behaviortree_ros2/          # imported by vcstool, git-ignored
├── models/                         # network weights, Git LFS
├── docker/
├── .devcontainer/
├── dependencies.repos
└── docker-compose.dev.yml
```

## Institution

Developed at Brno University of Technology (BUT)  
Faculty of Mechanical Engineering (FME)  
Brno, Czech Republic
