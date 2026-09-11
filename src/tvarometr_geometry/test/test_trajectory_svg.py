"""SVG must preserve physical geometry and never draw pen-up connections."""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tvarometr_geometry.trajectory_svg import INKSCAPE, trajectories_to_svg


def drawing():
    return {
        "labels": [
            [0, 0, 20],
            [0, 0, 0],
            [100, 50, 0],
            [100, 50, 20],
            [200, 0, 20],
            [200, 0, 0],
            [210, 0, 0],
            [210, 0, 20],
        ],
        "values": [],
        "erase": [],
        "values_bounds": [250, -100, 500, 100],
    }


def test_preserves_mm_scale_flips_y_and_breaks_at_pen_lifts():
    root = ET.fromstring(trajectories_to_svg(drawing()))
    _, _, width, height = map(float, root.get("viewBox").split())
    assert root.get("width") == f"{width:g}mm"
    assert root.get("height") == f"{height:g}mm"
    path = root.find(".//{*}g[@id='labels']/{*}path")
    assert path.get("d") == "M 0,0 L 100,-50 M 200,0 L 210,0"
    travel = root.find(".//{*}path[@id='travel-labels']")
    assert travel.get("d") == "M 100,-50 L 200,0"


def test_inkscape_layers_and_travel_visibility():
    for visible in (True, False):
        root = ET.fromstring(trajectories_to_svg(drawing(), show_travel=visible))
        for name in ("labels", "values", "erase", "grid", "legend", "travel"):
            layer = root.find(f".//{{*}}g[@id='{name}']")
            assert layer.get(f"{{{INKSCAPE}}}groupmode") == "layer"
        travel = root.find(".//{*}g[@id='travel']")
        assert (travel.get("style") == "display:none") != visible


@pytest.mark.parametrize(
    "point", [[1, 2], [1, 2, -1], [float("nan"), 0, 0], ["a", 0, 0]]
)
def test_bad_coordinates_are_rejected(point):
    data = drawing()
    data["labels"] = [point]
    with pytest.raises(ValueError, match="Invalid labels"):
        trajectories_to_svg(data)


def test_cli_exports_existing_json_with_default_svg_filename(tmp_path):
    source = tmp_path / "drahy.json"
    source.write_text(json.dumps(drawing()))
    script = Path(__file__).parents[1] / "tvarometr_geometry" / "trajectory_svg.py"
    subprocess.run([sys.executable, str(script), str(source)], check=True)
    assert ET.parse(source.with_suffix(".svg")).getroot().tag.endswith("svg")
    assert json.loads(source.read_text()) == drawing()


def test_cli_does_not_overwrite_input(tmp_path):
    source = tmp_path / "drahy.json"
    source.write_text(json.dumps(drawing()))
    script = Path(__file__).parents[1] / "tvarometr_geometry" / "trajectory_svg.py"
    result = subprocess.run(
        [sys.executable, str(script), str(source), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert json.loads(source.read_text()) == drawing()
