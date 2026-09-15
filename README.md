# Tvarometr - Automated Face Analysis and Robot Drawing System

An ABB GoFa photographs a visitor, neural networks estimate their age, gender and
emotion, and the robot writes the result on a whiteboard - then wipes it for the
next visitor. Built for events such as open days at Brno University of
Technology, Faculty of Mechanical Engineering.

> Being rebuilt on branch `rebuild-docker-bt`: Docker containers and a
> BehaviorTree.CPP orchestrator. Development containers are the only supported
> mode for now.

**Česky: [rychlý start pro vývoj](VYVOJ.md).**

## How a run goes

The operator starts each run from the keyboard. One run is:

1. Bring the robot to a photo pose.
2. Centre the visitor's face in the camera.
3. Estimate age, gender and emotion from one frame.
4. Generate the paths: the fixed labels, this visitor's values, and the sweep
   that wipes the values.
5. Write the labels (only on the first run - they stay on the board), then the
   values, and back off from the board.
6. Wait until the operator says the visitor is done, then wipe the values and
   back off again.

The development proceeds from the end of this list backwards. Steps 1, 4, 5 and
6 run for real against the robot; centring and inference are still faked in the
tree. See [Roadmap](#roadmap).

## Architecture

Four processes talk over ROS 2, spread over three containers:

| Node | Package | Container |
| --- | --- | --- |
| `orchestrator` - the behaviour tree | `tvarometr_orchestrator` | orchestrator |
| `trajectory_node`, `centring_node` | `tvarometr_geometry` | orchestrator |
| `usb_cam`, `inference_node` | `tvarometr_inference` | vision (GPU) |
| `robot_controller` | `robot_control` (separate repo) | driver |

### `tvarometr_orchestrator`

The BehaviorTree.CPP 4 tree in `behavior_trees/tvarometr.xml` drives everything
else. C++, one BT node per header/source pair.

- **Bring-up.** Before the first run the tree configures and activates the robot
  driver, unless it is active already - so restarting the orchestrator keeps the
  driver's robot session.
- **Each run** checks the driver is still active, asks it to make the robot
  ready (mastership, motors on, RAPID started), and then goes through the steps
  above. `board_written` on the blackboard remembers whether the labels are
  already up; it resets when the process restarts.
- **Operator keys.** `S` starts a run. After the values are drawn the run waits
  for `C` to wipe them. `E` aborts: it halts the running step and returns to
  waiting. The abort latches - `S` and `C` are refused until `Q` acknowledges it.
- An abort cancels the motion goal, but the driver lets the queued points run
  out, so it is an orderly stop and not an emergency stop.
- **Groot2** can attach to the running tree on port 1667 (`groot2_port`). The
  containers are on the host network, so there is nothing to map.

Stand-ins still in the tree: `MockAction name="CentreFace"` and `MockInference`,
which writes made-up attributes to the same port `RunInference` would. The real
`RunInference` node is already registered, so swapping it in is an XML edit.

### `tvarometr_geometry`

Python, no GPU. Plain nodes, not managed ones - they hold nothing that needs
loading, so they only need to be running.

- **`trajectory_node_exec`** answers `trajectory_node/generate_trajectories`
  with three `PoseArray`s in metres: labels, values and the wipe. A service,
  since it takes a couple of milliseconds. The Czech wording of the board text
  is decided here. The text generator is described in `TRAJECTORIES.md`.
- **`centring_node_exec`** will close the loop between the face detector and the
  robot. So far it only checks it can reach `inference_node/detect_face` and the
  driver's motion action.

### `tvarometr_inference`

- **`usb_cam`** streams the webcam on `/image_raw`.
- **`inference_node_exec`** is a managed node: configure loads the weights,
  activate starts accepting requests. It keeps only the newest frame.
  - `inference_node/run_inference` (action) runs YOLOv8 face detection, MiVOLO
    for age and gender and ResEmoteNet for emotion, and answers with
    `FaceAttributes`. Labels are the models' English ones.
  - `inference_node/detect_face` (service) runs the detector alone and returns
    the face bounding box - the cheap call the centring loop repeats.

Weights live in `models/` (Git LFS) and are mounted into the vision container at
`/opt/tvarometr/models`:

- `yolov8x_person_face.pt` - face detection
- `model_imdb_cross_person_4.22_99.46.pth.tar` - age and gender
- `affectnet7_model.pth` - emotion

### `tvarometr_interfaces`

`FaceAttributes` message, `RunInference` action, `DetectFace` and
`GenerateTrajectories` services.

### Robot driver

[abb_rws2_ros2_driver](https://github.com/Katzoun/abb_rws2_ros2_driver) lives in
its own repository and is imported with vcstool. It is a managed node offering
`robot_robtarget_move` and `robot_jointtarget_move` (actions) and
`controller_request` (service); its README documents them. This repo only builds
its production image and runs it.

## Getting started

### Requirements

- Ubuntu 22.04 with a native Docker Engine - not Docker Desktop, which cannot
  pass the GPU through. `docker context ls` should show `default` as active.
- NVIDIA GPU and NVIDIA Container Toolkit, for the vision container.
- Git LFS (`apt install git-lfs`) and vcstool (`apt install python3-vcstool`).
- An ABB GoFa with RWS 2.0, or RobotStudio's virtual controller.

### First run

On the host:

```bash
git clone https://github.com/Katzoun/tvarometr_ws.git
cd tvarometr_ws
git lfs install && git lfs pull       # weights; without LFS you get 130-byte pointers
vcs import src < dependencies.repos   # the robot driver and behaviortree_ros2
echo "CAMERA_DEVICE=/dev/video0" > .env
```

The import has to come before any image build: the orchestrator image resolves
dependencies from the driver's `robot_control_msgs` manifest. Both imported
repositories are git-ignored here; `vcs pull src` updates them.

`CAMERA_DEVICE` is mapped into the vision container when it is created, so set
it first. See [Environment](#environment).

### Containers

`docker-compose.dev.yml` defines three services over the one source tree:

| Service | Needs | Builds | Profile |
| --- | --- | --- | --- |
| `orchestrator` | CPU only | `tvarometr_orchestrator`, `tvarometr_geometry`, `tvarometr_interfaces` | none |
| `vision` | NVIDIA GPU | `tvarometr_inference`, `tvarometr_interfaces` | `vision` |
| `driver` | a robot | the driver's own production image | `robot` |

`orchestrator` and `vision` bind-mount the repo at `/workspace` and idle; you
start nodes from a terminal. `driver` starts the driver by itself.

**From the host, always name the service.** A plain `up -d --build` also rebuilds
and recreates the orchestrator, which kills a VS Code window attached to it.

### VS Code

Open the repo, run **Dev Containers: Reopen in Container** and pick
**orchestrator** or **vision**. Only that service starts, its packages build on
create, and the window's terminals run inside it. For both, open a second window
and pick the other one. Closing a window leaves its container running.

VS Code will not attach to a container created from the host with `compose up`
(it fails with `rmdir: Directory not empty`). Remove that one first with
`docker compose -f docker-compose.dev.yml rm -sf orchestrator` (or `vision`).

### Command line

```bash
docker compose -f docker-compose.dev.yml up -d --build orchestrator
docker compose -f docker-compose.dev.yml exec orchestrator bash
colcon build --symlink-install
```

For vision, add `--profile vision` and use `vision` as the service name.

Every shell sources ROS and the built workspace through `docker/ros-env.sh`; in a
shell that was open during a build, `source /opt/colcon_ws/install/setup.bash`.

## Running the system

Start the pieces in this order. All containers use the host network and the same
`ROS_DOMAIN_ID`, so the nodes find each other.

### 1. Robot driver - host

```bash
docker compose -f docker-compose.dev.yml --profile robot up -d --build --no-deps driver
docker logs -f abb_rws2_ros2_driver
```

The driver comes up `unconfigured`; the tree configures and activates it. Its
config (`src/abb_rws2_ros2_driver/robot_control/config/robot_control.yaml`) is
baked into the image, so after editing it run the same command again. The
driver repo's own `docker-compose.prod.yml` uses the same container name - run
it from one place only.

RAPID on the controller is maintained by hand, not from this repo.

### 2. Geometry nodes - orchestrator container

```bash
ros2 run tvarometr_geometry trajectory_node_exec
ros2 run tvarometr_geometry centring_node_exec     # not needed until centring is real
```

### 3. Vision - vision container

```bash
ros2 launch tvarometr_inference vision.launch.py    # use_camera:=false without a webcam
```

Until the tree brings inference up itself, drive it by hand:

```bash
ros2 lifecycle set /inference_node configure        # loads the weights, takes a while
ros2 lifecycle set /inference_node activate
ros2 topic hz /image_raw
ros2 action send_goal /inference_node/run_inference tvarometr_interfaces/action/RunInference {}
```

GPU check: `python3 -c 'import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))'`.

### 4. Orchestrator - orchestrator container

```bash
ros2 run tvarometr_orchestrator orchestrator_node
```

`ros2 run` and not `ros2 launch`, because launch does not pass the keyboard
through. Another tree: `--ros-args -p tree_file:=/workspace/path/to.xml`. The
process runs until Ctrl+C; a failed or aborted run returns to waiting for `S`.
If the driver cannot be brought up, the process exits.

## Working on the code

- **Python** - `--symlink-install` points the install at the source, so restart
  the node. Rebuild after adding entry points, launch or config files.
- **C++** - rebuild the package after every change.
- **Tree XML** - installed by symlink, so restart the orchestrator.
- **Interfaces** - after a change to `tvarometr_interfaces`, rebuild it and every
  package using it, in both containers.
- **Images** - after a change to a Dockerfile or requirements file, use **Dev
  Containers: Rebuild Container**.

Colcon writes to `/opt/colcon_ws/{build,install,log}` inside the container, never
into the repo. `docker/colcon-defaults-*.yaml` sets those paths and which
packages each container builds, so a bare `colcon build` is enough. Build output
survives a container restart and is gone after a rebuild.

Tests: `colcon test --packages-select tvarometr_geometry` (orchestrator) or
`tvarometr_inference` (vision), then `colcon test-result --verbose`.

| File | Role |
| --- | --- |
| `docker/orchestrator.Dockerfile`, `docker/vision.Dockerfile` | Dependencies only - no source, models or build. |
| `docker/requirements-*.txt` | Python pins; several are load-bearing and say why. |
| `docker-compose.dev.yml` | Mounts, GPU, camera, network, profiles. |
| `.devcontainer/orchestrator/`, `.devcontainer/vision/` | Which service VS Code attaches to, extensions, build on create. |
| `dependencies.repos` | Driver and behaviortree_ros2, for `vcs import`. |
| `docker/colcon-defaults-*.yaml` | Colcon paths and packages per container. |
| `docker/ros-env.sh`, `docker/entrypoint.sh` | Source ROS in every shell and in the container command. |

## Configuration

### Robot

Address and credentials are in the driver's `robot_control.yaml`. The virtual
controller listens on port 80, the physical one on 443.

### Tree

Values meant to be tuned in the cell sit in `tvarometr.xml`: the photo pose
(`joints_deg`, degrees), the back-off and approach points (`x,y,z,qx,qy,qz,qw`,
metres, ROS quaternion order), speeds, and the `tool`/`wobj` names, which must
exist on the controller. An empty `wobj` means `wobj0`. RAPID shows the
quaternion as `[qw,qx,qy,qz]`.

### Inference

`tvarometr_inference/config/inference.yaml` - device, weights directory, image
topic. `config/usb_cam.yaml` - resolution, framerate, video device. Both are read
at startup; restart the launch after editing.

### Trajectories

`trajectory_node` parameters: letter height and spacing, width of the value
column, eraser width, pen orientation. Set with `--ros-args -p name:=value`.

### Environment

Optional `.env` in the repo root, read by Compose:

| Variable | Default | Effect |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `42` | DDS domain for all three containers |
| `CAMERA_DEVICE` | `/dev/null` | Host webcam passed to vision as `/dev/video0` |

## Roadmap

Next, in order:

1. **Inference on its own** - models on the GPU, a real frame from the webcam,
   `RunInference` answering by hand in the vision container.
2. **Inference in the tree** - bring the inference node up next to the driver,
   check it every run, and replace `MockInference` with `RunInference`.
3. **Real photo pose** - jog the robot to it and write the joints into the tree.
4. **Face centring** - a `CentreFace` action served by `centring_node`: detect
   the face, move the robot a little, wait for a frame taken after it stopped,
   repeat until the face is centred or time runs out. Still open: how the camera
   is mounted, and whether to turn the camera or move it.

Known gaps, left for later: an abort while drawing leaves a dirty board; the
eraser has no tooldata of its own yet; the driver's RWS timeout can be too short
for `make_robot_ready`.

## Project structure

```
tvarometr_ws/
├── src/
│   ├── tvarometr_orchestrator/     # behaviour tree (C++)
│   │   ├── behavior_trees/tvarometr.xml
│   │   └── include/, src/          # one BT node per pair; orchestrator_node.cpp is main
│   ├── tvarometr_geometry/         # trajectory and centring nodes (Python)
│   ├── tvarometr_inference/        # camera and the networks (Python, GPU)
│   │   ├── config/                 # inference.yaml, usb_cam.yaml
│   │   └── tvarometr_inference/vendor/   # MiVOLO and ResEmoteNet, as-is
│   ├── tvarometr_interfaces/       # msg, srv, action
│   ├── master_pkg/                 # the old state-machine system, not built
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
