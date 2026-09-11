"""Convert the trajectory generator's JSON to a layered SVG at 1 unit = 1 mm."""

import argparse
import itertools
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

SVG = "http://www.w3.org/2000/svg"
INKSCAPE = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG)
ET.register_namespace("inkscape", INKSCAPE)

COLORS = {"labels": "#2166ac", "values": "#16804a", "erase": "#e08214"}


def _element(parent, tag, **attributes):
    return ET.SubElement(
        parent,
        f"{{{SVG}}}{tag}",
        {key.replace("_", "-"): str(value) for key, value in attributes.items()},
    )


def _layer(root, name, label, hidden=False):
    group = _element(root, "g", id=name)
    group.set(f"{{{INKSCAPE}}}groupmode", "layer")
    group.set(f"{{{INKSCAPE}}}label", label)
    if hidden:
        group.set("style", "display:none")
    return group


def _path_data(points, contact=True):
    """Break at every lift, preventing lines between independent pen strokes."""
    commands = []
    connected = False
    for start, end in itertools.pairwise(points):
        down = start[2] == end[2] == 0
        if down != contact or start[:2] == end[:2]:
            connected = False
            continue
        if not connected:
            commands.append(f"M {start[0]:.9g},{-start[1]:.9g}")
        commands.append(f"L {end[0]:.9g},{-end[1]:.9g}")
        connected = True
    return " ".join(commands)


def _numbers(value, size):
    return (
        isinstance(value, (list, tuple))
        and len(value) == size
        and all(type(v) in (int, float) and math.isfinite(v) for v in value)
    )


def trajectories_to_svg(data: dict, *, grid_step=50.0, show_travel=False) -> str:
    """Render XY centerlines; Z selects contact/travel, not a 3D projection.

    Physical SVG dimensions in mm match the viewBox dimensions. The Y axis
    is inverted for SVG so text retains the generator's upward-positive Y.
    Eraser footprint size is absent from JSON; only its centerline is shown.
    """
    if not math.isfinite(grid_step) or grid_step <= 0:
        raise ValueError("grid_step must be finite and positive")
    if not isinstance(data, dict):
        raise TypeError("Expected a JSON object with labels, values and erase")
    positions = []
    for name in COLORS:
        points = data.get(name)
        if not isinstance(points, list):
            raise TypeError(f"{name} must be a list of [x, y, z] points")
        for index, point in enumerate(points):
            if not _numbers(point, 3) or point[2] < 0:
                raise ValueError(
                    f"Invalid {name}[{index}]: expected finite x, y, z with z >= 0"
                )
            positions.append(point[:2])
    bounds = data.get("values_bounds")
    if bounds is not None:
        if not _numbers(bounds, 4) or bounds[0] > bounds[2] or bounds[1] > bounds[3]:
            raise ValueError("Invalid values_bounds: expected [xmin, ymin, xmax, ymax]")
        positions.extend([bounds[:2], bounds[2:]])
    if not positions:
        raise ValueError("No points or bounds to visualize")
    positions.append((0, 0))
    xmin = math.floor(min(p[0] for p in positions) / grid_step) * grid_step
    ymin = math.floor(min(p[1] for p in positions) / grid_step) * grid_step
    xmax = math.ceil(max(p[0] for p in positions) / grid_step) * grid_step
    ymax = math.ceil(max(p[1] for p in positions) / grid_step) * grid_step
    # Reserve enough room for the legend without changing the geometry scale.
    xmax = max(xmax, xmin + 8 * grid_step)
    ymax = max(ymax, ymin + 2 * grid_step)
    nx = round((xmax - xmin) / grid_step)
    ny = round((ymax - ymin) / grid_step)
    if nx + ny > 2000:
        raise ValueError("Grid too dense; increase --grid-step")
    margin = grid_step * 0.6
    width = xmax - xmin + 2 * margin
    height = ymax - ymin + 3 * margin
    root = ET.Element(
        f"{{{SVG}}}svg",
        {
            "version": "1.1",
            "width": f"{width:.12g}mm",
            "height": f"{height:.12g}mm",
            "viewBox": f"{xmin - margin:.12g} {-ymax - margin:.12g} {width:.12g} {height:.12g}",
        },
    )
    _element(root, "title").text = "Trajectories (mm)"
    _element(
        root, "desc"
    ).text = "Scale 1:1 in mm. X right, Y up. Eraser centerline only."
    background = _layer(root, "background", "Background")
    _element(
        background,
        "rect",
        x=xmin - margin,
        y=-ymax - margin,
        width=width,
        height=height,
        fill="white",
    )
    grid = _layer(root, "grid", f"Grid ({grid_step:g} mm)")
    for axis, count, minimum in (("x", nx, xmin), ("y", ny, ymin)):
        for i in range(count + 1):
            value = minimum + i * grid_step
            if axis == "x":
                x1, y1, x2, y2 = value, -ymax, value, -ymin
                tx, ty, anchor = value, -ymin + margin * 0.35, "middle"
            else:
                x1, y1, x2, y2 = xmin, -value, xmax, -value
                tx, ty, anchor = xmin - margin * 0.15, -value, "end"
            _element(
                grid,
                "line",
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                stroke="#94a3b8" if value == 0 else "#e2e8f0",
                stroke_width=grid_step * (0.012 if value == 0 else 0.005),
            )
            _element(
                grid,
                "text",
                x=tx,
                y=ty,
                text_anchor=anchor,
                dominant_baseline="middle",
                font_size=grid_step * 0.15,
                font_family="sans-serif",
                fill="#475569",
            ).text = f"{value:g}"
    if bounds is not None:
        area = _layer(root, "values-area", "Values bounds")
        left, bottom, right, top = bounds
        _element(
            area,
            "rect",
            x=left,
            y=-top,
            width=right - left,
            height=top - bottom,
            fill="none",
            stroke="#64748b",
            stroke_width=0.4,
            stroke_dasharray="3 3",
        )
    for name, label in (
        ("erase", "Erase (centerline)"),
        ("labels", "Labels"),
        ("values", "Values"),
    ):
        layer = _layer(root, name, label)
        _element(
            layer,
            "path",
            d=_path_data(data[name]),
            fill="none",
            stroke=COLORS[name],
            stroke_width=0.45 if name == "erase" else 0.9,
            stroke_opacity=0.6 if name == "erase" else 1,
            stroke_linecap="round",
            stroke_linejoin="round",
        )
    travel = _layer(root, "travel", "Travel (tool lifted)", hidden=not show_travel)
    for name in COLORS:
        _element(
            travel,
            "path",
            id=f"travel-{name}",
            d=_path_data(data[name], False),
            fill="none",
            stroke="#94a3b8",
            stroke_width=0.3,
            stroke_dasharray="2 2",
        )
    legend = _layer(root, "legend", "Legend")
    legend.set("font-family", "sans-serif")
    legend.set("font-size", str(grid_step * 0.15))
    _element(
        legend, "text", x=xmin, y=-ymax - margin * 0.4, fill="#334155"
    ).text = "XY (mm) · 1:1"
    for i, (name, label) in enumerate(
        (("labels", "Labels"), ("values", "Values"), ("erase", "Erase (centerline)"))
    ):
        _element(
            legend,
            "text",
            x=xmin + i * grid_step * 1.6,
            y=-ymin + margin * 1.1,
            fill=COLORS[name],
        ).text = label
    bar_x, bar_y = xmax - 2 * grid_step, -ymin + margin * 0.85
    _element(
        legend,
        "path",
        d=f"M {bar_x},{bar_y} h {2 * grid_step}",
        stroke="#334155",
        stroke_width=0.8,
    )
    _element(
        legend,
        "text",
        x=bar_x + grid_step,
        y=bar_y + grid_step * 0.2,
        text_anchor="middle",
        fill="#334155",
    ).text = f"{2 * grid_step:g} mm"
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description="Trajectory JSON to SVG (mm)")
    parser.add_argument("input", type=Path, help="JSON from --all-paths")
    parser.add_argument(
        "output", type=Path, nargs="?", help="Output SVG (default: input.svg)"
    )
    parser.add_argument(
        "--grid-step", type=float, default=50.0, help="Grid spacing (mm)"
    )
    parser.add_argument("--show-travel", action="store_true", help="Show travel moves")
    args = parser.parse_args()
    output = args.output or args.input.with_suffix(".svg")
    if output.resolve() == args.input.resolve():
        parser.error("Input and output must be different files")
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        svg = trajectories_to_svg(
            data, grid_step=args.grid_step, show_travel=args.show_travel
        )
        output.write_text(svg, encoding="utf-8")
    except (OSError, TypeError, ValueError) as error:
        parser.error(str(error))
    print(f"Saved '{output}' (1 unit = 1 mm).")


if __name__ == "__main__":
    main()
