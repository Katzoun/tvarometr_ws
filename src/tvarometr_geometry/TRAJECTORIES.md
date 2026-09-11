# Trajectories

Python tools; no ROS or robot connection required.

## Generate

```bash
python3 -m pip install svg.path==7.0
python3 src/tvarometr_geometry/tvarometr_geometry/path_generator.py \
  '32\nmuž\nšťastný' 60 10 drahy.json --all-paths \
  --values-width 600 --eraser-width 20
```

Input: three lines containing age, gender and mood. Output:

| Key | Content |
| --- | --- |
| `labels` | Fixed board text: Věk, Pohlaví, Nálada |
| `values` | Input values in the right column |
| `erase` | Overlapping sweeps over the fixed values area |
| `values_bounds` | `[xmin, ymin, xmax, ymax]` in mm |

Points are `[x, y, z]` in mm: X right, Y up, first baseline Y=0.
Z=0 means contact; Z=20 means lifted. Each path starts and ends lifted.
Use `labels` + `values` initially, then `erase` and new `values`.
Cycle state, tool changes and robot coordinates belong to the caller.

Keep layout parameters constant across cycles. Oversized text is rejected.
Set `--eraser-width` to the effective circular footprint diameter; its radius
extends beyond `values_bounds`. `--label-gap` adds clearance (default 10 mm).
Board dimensions are not checked.

```python
from tvarometr_geometry.path_generator import generate_trajectories

paths = generate_trajectories("32\nmuž\nšťastný", values_width=600, eraser_width=20)
```

`generate_path(text, ...)` accepts arbitrary text; CLI without `--all-paths`
exports headerless CSV. The bundled Relief SingleLine font supports Czech
accents. Height uses nominal capitals; spacing adds to font advance widths.
Default contact step limit: 15 mm; curve tolerance: 0.1 mm.

## View

```bash
python3 src/tvarometr_geometry/tvarometr_geometry/trajectory_svg.py drahy.json
```

Open `drahy.svg` in Inkscape. No extra Python dependencies.

- Physical scale: **1 SVG unit = 1 mm**; grid: 50 mm.
- Layers: labels (blue), values (green), erase (orange), bounds, grid, legend.
- Travel is hidden by default; toggle it in Inkscape's Layers panel.
- Erase shows the centerline; the JSON does not include the tool diameter.
- Board text comes directly from the JSON geometry.

```bash
python3 src/tvarometr_geometry/tvarometr_geometry/trajectory_svg.py \
  drahy.json preview.svg --grid-step 25 --show-travel
```

After building the ROS package, use `ros2 run tvarometr_geometry` with
`generate_text_path` or `trajectory_svg` and the same arguments.

## Tests

```bash
PYTHONPATH=src/tvarometr_geometry python3 -m pytest src/tvarometr_geometry/test
```
