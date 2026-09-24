#!/usr/bin/env bash
# Brings a run up: the three production containers, and then the command for
# the tree, which is left to you because it reads the keyboard.
#
#   ./start.sh           start whatever is not running
#   ./start.sh --build   rebuild the images first, then start
#   ./start.sh --stop    stop and remove the containers

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

COMPOSE=(docker compose -f docker-compose.yml)
ORCHESTRATOR=tvarometr_orchestrator_prod
CONTAINERS=(tvarometr_orchestrator_prod tvarometr_inference_prod abb_rws2_ros2_driver_prod)

case "${1:-}" in
  "")      build=() ;;
  --build) build=(--build) ;;
  --stop)  exec "${COMPOSE[@]}" down ;;
  *)       echo "usage: $0 [--build|--stop]" >&2; exit 1 ;;
esac

# The dev stack speaks on the same ROS_DOMAIN_ID. Two centring nodes both take
# the same goal, and only one of the two answers is the one being read.
dev=$(docker ps --format '{{.Names}}' \
  | grep -E '^(tvarometr_(orchestrator|inference)_dev|abb_rws2_ros2_driver)$' || true)
if [ -n "$dev" ]; then
  echo "The dev containers are up:" >&2
  sed 's/^/  /' <<<"$dev" >&2
  echo "Stop them first - their nodes would answer alongside these." >&2
  exit 1
fi

# Docker creates the inference container and only then refuses to start it, in one
# line among its own output. An unplugged webcam is worth half an hour of
# looking in the wrong place, so ask before starting anything.
camera=${CAMERA_DEVICE:-/dev/video0}
if [ ! -c "$camera" ]; then
  cat >&2 <<MESSAGE
No camera at $camera, so the inference container will not start.

Plug the webcam back in, or name the device you do have:

  CAMERA_DEVICE=/dev/video2 $0
  CAMERA_DEVICE=/dev/null $0     everything except the camera

MESSAGE
  exit 1
fi

"${COMPOSE[@]}" up -d "${build[@]}"

# A container that dies on startup would otherwise show up only as nodes that
# never appear, one timeout at a time.
for name in "${CONTAINERS[@]}"; do
  # A missing container leaves a blank line on stdout as well as the error.
  state=$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || true)
  state=${state//[[:space:]]/}
  if [ "$state" = running ]; then
    continue
  fi
  echo "$name is ${state:-missing}." >&2
  logs=$(docker logs --tail 20 "$name" 2>&1 || true)
  if [ -n "$logs" ]; then
    echo "Its last lines:" >&2
    sed 's/^/  /' <<<"$logs" >&2
  fi
  exit 1
done

# Every node the tree looks for at bring-up. It configures and activates the
# managed ones itself, so here they only have to exist.
missing=0
wait_for() {
  local node=$1 left=${2:-60}
  while ! docker exec "$ORCHESTRATOR" /entrypoint.sh ros2 node list 2>/dev/null | grep -qx "$node"; do
    if [ "$left" -le 0 ]; then
      echo "  $node - not up" >&2
      missing=1
      return
    fi
    sleep 2
    left=$((left - 2))
  done
  echo "  $node"
}

echo "Waiting for the nodes:"
wait_for /robot_controller
wait_for /trajectory_node
wait_for /centring_node
wait_for /camera
wait_for /inference_node 120

[ "$missing" -eq 0 ] || echo "
Something above is missing; '${COMPOSE[*]} logs' says why."

cat <<MESSAGE

Start the tree, which wants a keyboard of its own:

  docker exec -it $ORCHESTRATOR /entrypoint.sh ros2 run tvarometr_orchestrator orchestrator_node

S starts a run, C repeats a failed search or erases the board, E aborts and Q
acknowledges it. Groot2 connects to localhost:1667.

  ${COMPOSE[*]} logs -f inference   what the camera and the models are doing
  ./start.sh --stop              put it all down
MESSAGE
