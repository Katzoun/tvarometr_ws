# Rychlý start pro vývoj

Úplný popis je v [README](README.md#getting-started), tohle je zkrácená verze.

Máš dvě prostředí: **orchestrator** pro chování systému a **vision** pro kameru
a neuronové sítě. Obě vidí stejný repozitář, ale každé má vlastní knihovny
i výsledky sestavení. Vision potřebuje NVIDIA GPU a NVIDIA Container Toolkit,
orchestrátor běží kdekoli.

Ovladač robota se tu nevyvíjí — má vlastní repozitář
[abb_rws2_ros2_driver](https://github.com/Katzoun/abb_rws2_ros2_driver)
i vlastní devcontainer. Tenhle stack ho umí jen spustit, za profilem `robot`.

## 1. Připrav si repozitář

Na hostiteli, ještě před otevřením kontejneru:

```bash
git lfs install && git lfs pull      # váhy modelů; bez LFS dostaneš jen ukazatele
vcs import src < dependencies.repos        # ovladač robota z jeho repozitáře
```

Import musí proběhnout **před** stavbou obrazů. Orchestrátor je v C++ a potřebuje
hlavičky z `robot_control_msgs`, takže jeho image sahá na manifest ovladače —
bez importu build spadne na chybějícím souboru.

Pak otevři repozitář ve VS Code, přes `F1` spusť **Dev Containers: Reopen in
Container** a vyber jedno z prostředí.

VS Code kontejner připraví a sestaví jeho ROS balíčky. Terminály v tom okně pak
běží uvnitř kontejneru. Sám o sobě kontejner nespustí nic.

Pro souběžnou práci otevři repozitář ve druhém okně a vyber druhé prostředí.
Zavření okna kontejnery nevypíná; zastavíš je z terminálu hostitele:

```bash
docker compose -f docker-compose.dev.yml --profile vision --profile robot stop
```

## 2. Spusť uzel

V prostředí **orchestrator**:

```bash
ros2 launch tvarometr_orchestrator orchestrator.launch.py
```

Strom proběhne jednou a proces s ním skončí — není to démon, pouštíš ho, když je
co kreslit. Zatím je to kostra s jediným logovacím uzlem.

V prostředí **vision**:

```bash
ros2 launch tvarometr_inference vision.launch.py device:=cuda:0 use_camera:=false
```

Uzel naběhne ve stavu `unconfigured` a nemá načtené váhy. Konfigurace je načte,
což chvíli trvá, aktivace mu pak dovolí přijímat goaly:

```bash
ros2 lifecycle set /inference_node configure
ros2 lifecycle set /inference_node activate
```

Sítě pustíš na poslední snímek přes action:

```bash
ros2 action send_goal /inference_node/run_inference \
    tvarometr_interfaces/action/RunInference {}
```

Ovladač robota spustíš z jeho vlastního kontejneru, postup je v jeho README.
Oba kontejnery běží na síti hostitele se stejným `ROS_DOMAIN_ID`, takže se
jejich uzly navzájem vidí.

## 3. Upravuj kód

Uprav Python soubor, zastav uzel přes `Ctrl+C` a spusť `ros2 launch` znovu.
Zdrojáky se ukládají přímo do repozitáře na hostiteli.

Po změně ROS zpráv, akcí, entry pointů nebo launch/config souborů sestav
balíčky znovu a načti výsledek:

```bash
# v orchestrator
colcon build --symlink-install --packages-select \
    robot_control_msgs tvarometr_interfaces tvarometr_orchestrator
# ve vision
colcon build --symlink-install --packages-select tvarometr_interfaces tvarometr_inference

source /opt/colcon_ws/install/setup.bash
```

V C++ se navíc musí přestavět po každé změně zdrojáku, `--symlink-install` tam
narozdíl od Pythonu nic neušetří.

Po změně knihoven nebo Dockerfile použij **Dev Containers: Rebuild Container**.

## Dva různé buildy

| Operace | Co připravuje | Kdy ji potřebuješ |
| --- | --- | --- |
| Docker build | Image se systémem, ROS a knihovnami. | Poprvé a po změně závislostí nebo Dockerfile. |
| Colcon build | Tvoje ROS balíčky: rozhraní, spustitelné příkazy, instalaci. | Automaticky při vytvoření kontejneru, pak ručně po změně rozhraní. |

## Kde jsou soubory

```text
/workspace/              repozitář sdílený s hostitelem
/opt/colcon_ws/build/    pracovní soubory Colconu v kontejneru
/opt/colcon_ws/install/  sestavené ROS balíčky v kontejneru
/opt/colcon_ws/log/      záznamy sestavení v kontejneru
```

Cesta `/opt/colcon_ws` se na hostitele nemountuje, takže build ani install se
ti do repozitáře nikdy nepropíšou. Přežijí zastavení a spuštění kontejneru, ale
při **Rebuild Container** zmizí — každý rebuild tak začíná načisto.
