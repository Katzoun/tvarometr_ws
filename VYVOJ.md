# Rychlý start pro vývoj

Zkrácená česká verze. Všechno podrobně, včetně vysvětlení, je v [README](README.md).

## Co systém dělá a kde je vývoj

Robot najede do fotopozice, vycentruje obličej, sítě odhadnou věk, pohlaví
a náladu, robot to napíše na tabuli a po klávese **C** hodnoty smaže. Popisky
(Věk, Pohlaví, Nálada) píše jen v prvním běhu.

Vyvíjí se od konce. Reálně s robotem už jede fotopozice, generování trajektorií,
psaní, odjetí od tabule a mazání. Centrování a inference jsou ve stromu zatím
falešné. Co přijde dál, je v [Roadmap](README.md#roadmap).

## Prostředí

| Kontejner | Na co | Jak ho spustit |
| --- | --- | --- |
| **orchestrator** | strom, generování trajektorií, centrování | VS Code → *Reopen in Container* |
| **inference** | kamera a sítě, potřebuje NVIDIA GPU | VS Code → *Reopen in Container* |
| **driver** | ovladač robota, hotový image | z hostitele, viz níže |

Před prvním otevřením na hostiteli:

```bash
git lfs install && git lfs pull
vcs import src < dependencies.repos
```

Kontejner inference čeká webkameru na `/dev/video0` a bez ní nenaběhne. Jinou kameru nebo
žádnou (`/dev/null`) nastavíš proměnnou `CAMERA_DEVICE`, viz
[Environment](README.md#environment).

**Z hostitele vždycky piš název služby.** `docker compose ... up -d --build`
bez něj přestaví i orchestrátor a shodí ti otevřený devcontainer.

## Spuštění běhu

1. **Driver** (hostitel). Naběhne `unconfigured`, zapne ho až strom.

   ```bash
   docker compose -f docker-compose.dev.yml --profile robot up -d --build --no-deps driver
   ```

   Konfigurace driveru je zapečená v image, takže po úpravě `robot_control.yaml`
   stejný příkaz zopakuj.

2. **Trajektorie** (orchestrator):

   ```bash
   ros2 run tvarometr_geometry trajectory_node_exec
   ```

3. **Centrování** (orchestrator, druhý terminál):

   ```bash
   ros2 launch tvarometr_geometry centring.launch.py
   ```

   Limity `min_z` a `max_z` a ostatní nastavení jsou v
   `src/tvarometr_geometry/config/centring.yaml`. Než to pustíš proti robotu,
   zkus to s `dry_run: true`: uzel projde celou smyčku a vypíše, kam by jel.

4. **Strom** (orchestrator, třetí terminál):

   ```bash
   ros2 run tvarometr_orchestrator orchestrator_node
   ```

   **S** spustí běh, **C** po napsání pustí mazání, **E** přeruší a **Q**
   přerušení kvituje. Dokud ho nekvituješ, S i C jsou odmítnuté. `ros2 run`,
   ne `ros2 launch`, jinak se klávesy k uzlu nedostanou. Groot2 na hostiteli se
   připojí na `localhost:1667`.

## Inference

```bash
ros2 launch tvarometr_inference inference.launch.py
ros2 run rqt_image_view rqt_image_view /inference_node/debug_image   # lidé, obličeje, popisky, koho vybral
ros2 run rqt_image_view rqt_image_view /inference_node/scene_image   # co ukáže televize
ros2 lifecycle set /inference_node configure   # načte váhy
ros2 lifecycle set /inference_node activate
ros2 action send_goal /inference_node/run_inference tvarometr_interfaces/action/RunInference {}
```

Kameru samotnou, třeba na ladění, pustíš přes `camera.launch.py`. Nastavení je
v `src/tvarometr_inference/config/`, po úpravě restartuj launch:

- `inference.yaml`: zařízení, složka s vahami, topic kamery a výběr návštěvníka:
  `min_person_width_px`, svislice nad značkou na zemi `axis_x` a `axis_falloff`.
  Za běhu je měníš přes `ros2 param set /inference_node axis_x 0.45` (vždy s
  desetinnou tečkou) a v debug obraze hned vidíš, kde svislice je.
- `usb_cam.yaml`: rozlišení a fps
- `camera_controls.yaml`: expozice, ostření, vyvážení bílé (názvy podle
  `v4l2-ctl -d /dev/video0 --list-ctrls-menus`)

## Kdy co přestavět

| Změna | Co udělat |
| --- | --- |
| Python, XML stromu | restartovat uzel |
| C++ | `colcon build` a restart |
| rozhraní, entry pointy, nové launch/config soubory | `colcon build` v obou kontejnerech, `source /opt/colcon_ws/install/setup.bash` |
| Dockerfile, requirements | *Dev Containers: Rebuild Container* |

Build a install jsou v `/opt/colcon_ws` uvnitř kontejneru, do repa se nepropíšou
a rebuild kontejneru je smaže.
