# Rychlý start pro vývoj

Zkrácená česká verze, podrobnosti jsou v [README](README.md).

Robot najede do fotopozice, vycentruje obličej, sítě odhadnou věk, pohlaví
a náladu, robot to napíše na tabuli a po **C** hodnoty smaže. Popisky píše jen
v prvním běhu. Co zbývá doladit, je v [Roadmap](README.md#roadmap).

## Prostředí

| Kontejner | Na co | Jak ho spustit |
| --- | --- | --- |
| **orchestrator** | strom, trajektorie, centrování | VS Code → *Reopen in Container* |
| **inference** | kamera a sítě, NVIDIA GPU | VS Code → *Reopen in Container* |
| **driver** | ovladač robota, hotový image | z hostitele, viz níže |

Před prvním otevřením na hostiteli:

```bash
git lfs install && git lfs pull
vcs import src < dependencies.repos
```

Inference čeká webkameru na `/dev/video0`; jinou nebo žádnou nastavíš přes
`CAMERA_DEVICE` ([Environment](README.md#environment)).

**Z hostitele vždycky piš název služby**, jinak se přestaví i orchestrátor a
shodí otevřený devcontainer.

## Ostrý běh

Prod kontejnery mají zdroj i váhy uvnitř image: nic se nemountuje a na stroji,
kde to jede, se nic nepřekládá. Dev kontejnery musí být zastavené - mluví na
stejném `ROS_DOMAIN_ID` a uzly by si odpovídaly navzájem.

```bash
./start.sh --build   # poprvé a po každé změně zdroje
./start.sh           # jen nastartovat
./start.sh --stop
```

Skript zapne `orchestrator` (trajektorie a centrování), `inference` (kamera
a sítě) a `driver`, počká až uzly naběhnou a vypíše příkaz pro strom. Nejdřív ale
zkontroluje kameru: Docker kontejner bez ní nejdřív vytvoří a teprve pak ho
odmítne spustit, a ta hláška se v jeho výpisu snadno přehlédne. Jinou kameru
nebo běh bez ní:

```bash
CAMERA_DEVICE=/dev/video2 ./start.sh
CAMERA_DEVICE=/dev/null ./start.sh     # všechno kromě kamery
```

Když některý kontejner po startu neběží, skript vypíše jeho stav a posledních
dvacet řádků logu místo toho, aby čekal na uzly, které se nikdy neobjeví. Strom není
službou, protože čte klávesnici:

```bash
docker exec -it tvarometr_orchestrator_prod /entrypoint.sh ros2 run tvarometr_orchestrator orchestrator_node
```

Lifecycle driveru i inference si strom udělá sám. Debug obraz jde pustit
i z ostrého běhu, `DISPLAY` a X socket kontejner má:

```bash
docker exec -it tvarometr_inference_prod /entrypoint.sh \
  ros2 run rqt_image_view rqt_image_view /inference_node/debug_image/compressed
```

Zbytek téhle stránky je vývojová cesta přes bind mount.

## Spuštění běhu

1. **Driver** (hostitel), zapne ho až strom. Po úpravě `robot_control.yaml` příkaz zopakuj.

   ```bash
   docker compose -f docker-compose.dev.yml --profile robot up -d --build --no-deps driver
   ```

2. **Inference** (inference kontejner), viz [níže](#inference).

3. **Trajektorie a centrování** (orchestrator, každý v jiném terminálu). Limity
   a `dry_run` jsou v `src/tvarometr_geometry/config/centring.yaml`.

   ```bash
   ros2 run tvarometr_geometry trajectory_node_exec
   ros2 launch tvarometr_geometry centring.launch.py
   ```

4. **Strom** (orchestrator, další terminál). Driver i inferenci zapne sám; když
   některý nenajde, skončí.

   ```bash
   ros2 run tvarometr_orchestrator orchestrator_node
   ```

   **S** spustí běh, **C** zopakuje neúspěšné hledání nebo pustí mazání, **E**
   přeruší a **Q** přerušení kvituje. `ros2 run`, ne `launch`, jinak nechodí klávesy.
   Groot2 se připojí na `localhost:1667`.

## Inference

```bash
ros2 launch tvarometr_inference inference.launch.py
ros2 run rqt_image_view rqt_image_view /inference_node/debug_image/compressed   # koho vybral a proč
ros2 run rqt_image_view rqt_image_view /inference_node/scene_image/compressed   # co ukáže televize
ros2 lifecycle set /inference_node configure   # jen bez stromu
ros2 lifecycle set /inference_node activate
ros2 action send_goal -f /inference_node/run_inference tvarometr_interfaces/action/RunInference {}
```

Samotnou kameru pustíš přes `camera.launch.py`. Nastavení je v
`src/tvarometr_inference/config/`, po úpravě restartuj launch:

- `inference.yaml`: výběr návštěvníka (`min_face_height_px`,
  `min_person_width_px`, `axis_x`, `axis_falloff`, za běhu
  `ros2 param set /inference_node axis_x 0.45`) a průměrování (`samples`,
  `min_samples`, `sample_timeout_s`)
- `camera.yaml`: rozlišení a fps podle `v4l2-ctl -d /dev/video0 --list-formats-ext`
- `camera_controls.yaml`: expozice, ostření, vyvážení bílé

## Kdy co přestavět

| Změna | Co udělat |
| --- | --- |
| Python, XML stromu | restartovat uzel |
| C++ | `MAKEFLAGS=-j2 colcon build --parallel-workers 1` a restart |
| rozhraní, entry pointy, nové launch/config soubory | build v obou kontejnerech, `source /opt/colcon_ws/install/setup.bash` |
| Dockerfile, requirements | *Dev Containers: Rebuild Container* |
| cokoli, a chceš to v ostrém běhu | `./start.sh --build` |

C++ build vždycky s tímhle omezením, jinak dojde RAM. Build je v `/opt/colcon_ws`
v kontejneru a rebuild kontejneru ho smaže.
