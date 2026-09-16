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
| `camera`, `inference_node` | `tvarometr_inference` | inference (GPU) |
| `robot_controller` | `robot_control` (separate repo) | driver |

### `tvarometr_orchestrator`

The BehaviorTree.CPP 4 tree in `behavior_trees/tvarometr.xml` drives everything
else. C++, one BT node per header/source pair.

- **Bring-up.** Before the first run the tree configures and activates the robot
  driver and the inference node, each unless it is active already - so
  restarting the orchestrator keeps the driver's robot session and the weights
  on the GPU. The first configure of the inference node loads the weights and
  takes a while.
- **Each run** checks both are still active, asks it to make the robot
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

- **The scan and its retry.** A run drives to the photo pose and hands that pose
  to `CentreFace`. A scan that finds nobody puts the robot
  back on the photo pose and waits: `C` scans again, `E` gives up on the run.

Stand-in still in the tree: `MockInference`, which writes made-up attributes to
the same port `RunInference` would. The real `RunInference` node is already
registered, so swapping it in is an XML edit.

### `tvarometr_geometry`

Python, no GPU. Plain nodes, not managed ones - they hold nothing that needs
loading, so they only need to be running.

- **`trajectory_node_exec`** answers `trajectory_node/generate_trajectories`
  with three `PoseArray`s in metres: labels, values and the wipe. A service,
  since it takes a couple of milliseconds. The Czech wording of the board text
  is decided here. The text generator is described in `TRAJECTORIES.md`.
- **`centring_node_exec`** serves `centring_node/centre_face`: ask
  `inference_node/detect_face` where the visitor's face is, move the camera a
  little, ask again. Only Z changes - X, Y and the orientation stay those of the
  `photo_pose` in the goal, which is also what every step is measured from, so
  the robot's own position is never read. Z never leaves `[min_z, max_z]`, and a
  goal whose photo pose is already outside them is refused.
  - A face is about `face_height_m` tall, so its height in the frame turns the
    error in pixels into a move in metres. One step corrects `gain` of it, up to
    `max_step`.
  - With no face to measure it feels its way a blind `max_step` at a time
    towards the top of the visitor's body box, which is roughly where their head
    is: up when that runs off the top of the frame, down when they sit low in
    it. Seeing nobody at all means the camera is above everyone, so it feels
    downwards. A visitor whose head is already where a face belongs but whose
    face is turned away is waited out, not driven at.
  - It ends when the face sits within `tolerance` of `target_y`, or the camera
    reaches a Z limit with the face still off target - that is a success with
    `at_limit` set, because the face is in the frame either way. A Z limit with
    no face in view is a failure, as is running out of steps or time, or
    `max_lost_detections` useless answers in a row.
  - Settings are in `config/centring.yaml`; `dry_run` runs the whole loop and
    logs the moves without sending them to the robot.

### `tvarometr_inference`

- **`camera_node_exec`** reads the webcam through OpenCV and publishes its own
  JPEGs on `/image_raw/compressed`, undecoded. `camera.launch.py` sets the
  camera's V4L2 controls first and then starts it; `inference.launch.py`
  includes it. It replaces usb_cam, whose raw MJPEG mode segfaults in 0.8.1.
- **`inference_node_exec`** is a managed node: configure loads the weights,
  activate starts one thread that runs YOLOv8 on every new frame, publishes the
  images below and keeps the result. Nothing else touches the models, so a
  request never holds up the preview.
  - `inference_node/run_inference` (action) collects the visitor's face from
    `samples` frames, running MiVOLO for age and gender and ResEmoteNet for
    emotion on each, and answers with `FaceAttributes`: the median age and the
    averaged gender and emotion probabilities. Fewer than `min_samples` within
    `sample_timeout_s` fails the goal. Labels are the models' English ones.
  - `inference_node/detect_face` (service) answers from the latest analysed
    frame taken after `not_before`: where the visitor stands and where their face
    is - the cheap call the centring loop repeats.
  - Both work on the **visitor**: the person with the best box width times a
    weight for how far they are from `axis_x`, the vertical line over the floor
    mark where visitors stand. Somebody `axis_falloff` away from the line counts
    half. People narrower than `min_person_width_px` are too far away to count at
    all, and a runner-up scoring nearly as high is logged as ambiguous.
    Width, and the person rather than the face, because somebody standing close
    is cut off by the top or the bottom of the frame long before they are narrow:
    a child the camera looks over, or a tall visitor it sees the chest of. Their
    face then only says where to look, and `detect_face` reports it as missing
    rather than picking a bystander who happens to have one.
    There is no other rule and no memory between frames, so every call and the
    preview pick the same person from the same frame. Centring moves the camera
    only up and down, which changes neither where somebody stands across the
    image nor how wide they are, so the visitor keeps winning while it moves.
  - `/inference_node/scene_image/compressed` is for the TV beside the robot:
    plain boxes, the visitor's in green, the rest grey.
  - `/inference_node/debug_image/compressed` boxes everyone, labelled with their
    width and axis weight, the visitor in green and the people too far away in
    red, their faces outlined as well, with the axis in yellow and its
    half-weight distance dashed.
  - Both go out as JPEG on every analysed frame while something watches them.
    Age, gender and emotion are worked out only for `debug_image` and while a
    goal is collecting.

Weights live in `models/` (Git LFS) and are mounted into the inference container at
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
- NVIDIA GPU and NVIDIA Container Toolkit, for the inference container.
- Git LFS (`apt install git-lfs`) and vcstool (`apt install python3-vcstool`).
- An ABB GoFa with RWS 2.0, or RobotStudio's virtual controller.

### First run

On the host:

```bash
git clone https://github.com/Katzoun/tvarometr_ws.git
cd tvarometr_ws
git lfs install && git lfs pull       # weights; without LFS you get 130-byte pointers
vcs import src < dependencies.repos   # the robot driver and behaviortree_ros2
```

The import has to come before any image build: the orchestrator image resolves
dependencies from the driver's `robot_control_msgs` manifest. Both imported
repositories are git-ignored here; `vcs pull src` updates them.

The inference container expects the webcam at `/dev/video0` on the host and will
not start without it. See [Environment](#environment) for a different device or
none.

### Containers

`docker-compose.dev.yml` defines three services over the one source tree:

| Service | Needs | Builds | Profile |
| --- | --- | --- | --- |
| `orchestrator` | CPU only | `tvarometr_orchestrator`, `tvarometr_geometry`, `tvarometr_interfaces` | none |
| `inference` | NVIDIA GPU | `tvarometr_inference`, `tvarometr_interfaces` | `inference` |
| `driver` | a robot | the driver's own production image | `robot` |

`orchestrator` and `inference` bind-mount the repo at `/workspace` and idle; you
start nodes from a terminal. `driver` starts the driver by itself.

**From the host, always name the service.** A plain `up -d --build` also rebuilds
and recreates the orchestrator, which kills a VS Code window attached to it.

### VS Code

Open the repo, run **Dev Containers: Reopen in Container** and pick
**orchestrator** or **inference**. Only that service starts, its packages build on
create, and the window's terminals run inside it. For both, open a second window
and pick the other one. Closing a window leaves its container running.

VS Code will not attach to a container created from the host with `compose up`
(it fails with `rmdir: Directory not empty`). Remove that one first with
`docker compose -f docker-compose.dev.yml rm -sf orchestrator` (or `inference`).

### Command line

```bash
docker compose -f docker-compose.dev.yml up -d --build orchestrator
docker compose -f docker-compose.dev.yml exec orchestrator bash
colcon build --symlink-install
```

For inference, add `--profile inference` and use `inference` as the service name.

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
ros2 launch tvarometr_geometry centring.launch.py  # config:=... for another YAML
```

### 3. Inference - inference container

```bash
ros2 launch tvarometr_inference inference.launch.py   # use_camera:=false without a webcam
ros2 launch tvarometr_inference camera.launch.py      # or the camera alone, for tuning it
ros2 run rqt_image_view rqt_image_view /inference_node/debug_image/compressed   # faces, labels, who is picked
ros2 run rqt_image_view rqt_image_view /inference_node/scene_image/compressed   # what the TV shows
```

GUI tools open on the host display. The container reaches the host X server
through host networking, but the host has to let root in:
`xhost +SI:localuser:root`. The inference dev container runs that on the host
before it starts; after a new login, or for a container started from the command
line, run it yourself.

The tree configures and activates the node itself. To try it without the tree:

```bash
ros2 lifecycle set /inference_node configure        # loads the weights, takes a while
ros2 lifecycle set /inference_node activate
ros2 topic hz /image_raw/compressed
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
If the driver or the inference node cannot be brought up, the process exits -
so start the inference launch before the orchestrator.

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
`tvarometr_inference` (inference container), then `colcon test-result --verbose`.

| File | Role |
| --- | --- |
| `docker/orchestrator.Dockerfile`, `docker/inference.Dockerfile` | Dependencies only - no source, models or build. |
| `docker/requirements-*.txt` | Python pins; several are load-bearing and say why. |
| `docker-compose.dev.yml` | Mounts, GPU, camera, network, profiles. |
| `.devcontainer/orchestrator/`, `.devcontainer/inference/` | Which service VS Code attaches to, extensions, build on create. |
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

All in `tvarometr_inference/config/`, read at startup - restart the launch after
editing:

- `inference.yaml` - device, weights directory, image topic, how the visitor is
  picked, how many frames `RunInference` averages, JPEG quality. The selection
  parameters can also be changed live, which is the easy way to line the axis up
  with the floor mark: `ros2 param set /inference_node axis_x 0.45`.
- `camera.yaml` - video device, resolution, framerate, from the MJPG modes
  `v4l2-ctl -d /dev/video0 --list-formats-ext` lists. 30 fps allows a 33 ms
  exposure; the GPU analyses about 20 frames a second anyway.
- `camera_controls.yaml` - exposure, focus, white balance and the rest, under the
  names `v4l2-ctl -d /dev/video0 --list-ctrls-menus` shows.

### Trajectories

`trajectory_node` parameters: letter height and spacing, width of the value
column, eraser width, pen orientation. Set with `--ros-args -p name:=value`.

### Environment

Compose reads these from the host shell or from an optional `.env` in the repo
root. The camera is mapped when the container is created, so rebuild the inference
container after changing it.

| Variable | Default | Effect |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `42` | DDS domain for all three containers |
| `CAMERA_DEVICE` | `/dev/video0` | Host webcam passed to inference as `/dev/video0`; `/dev/null` on a machine without one |

## Roadmap

Next, in order:

1. **The scan against the robot** - `dry_run` first, then a small `gain`, and
   Z limits measured from the real photo pose.
2. **Real inference in the tree** - replace `MockInference` with `RunInference`.

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
