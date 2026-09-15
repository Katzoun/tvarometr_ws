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
| **vision** | kamera a sítě, potřebuje NVIDIA GPU | VS Code → *Reopen in Container* |
| **driver** | ovladač robota, hotový image | z hostitele, viz níže |

Před prvním otevřením na hostiteli:

```bash
git lfs install && git lfs pull
vcs import src < dependencies.repos
echo "CAMERA_DEVICE=/dev/video0" > .env    # kamera se mapuje jen při vytvoření kontejneru
```

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

3. **Strom** (orchestrator, druhý terminál):

   ```bash
   ros2 run tvarometr_orchestrator orchestrator_node
   ```

   **S** spustí běh, **C** po napsání pustí mazání, **E** přeruší a **Q**
   přerušení kvituje. Dokud ho nekvituješ, S i C jsou odmítnuté. `ros2 run`,
   ne `ros2 launch`, jinak se klávesy k uzlu nedostanou. Groot2 na hostiteli se
   připojí na `localhost:1667`.

## Inference (vision)

```bash
ros2 launch tvarometr_inference vision.launch.py
ros2 lifecycle set /inference_node configure   # načte váhy
ros2 lifecycle set /inference_node activate
ros2 action send_goal /inference_node/run_inference tvarometr_interfaces/action/RunInference {}
```

Zařízení, složka s vahami a topic kamery jsou v
`src/tvarometr_inference/config/inference.yaml`, kamera v `usb_cam.yaml`.
Po úpravě restartuj launch.

## Kdy co přestavět

| Změna | Co udělat |
| --- | --- |
| Python, XML stromu | restartovat uzel |
| C++ | `colcon build` a restart |
| rozhraní, entry pointy, nové launch/config soubory | `colcon build` v obou kontejnerech, `source /opt/colcon_ws/install/setup.bash` |
| Dockerfile, requirements | *Dev Containers: Rebuild Container* |

Build a install jsou v `/opt/colcon_ws` uvnitř kontejneru, do repa se nepropíšou
a rebuild kontejneru je smaže.
