"""Geometry checks without ROS, robot hardware or network access."""

import csv
import itertools
import json
import math
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from svg.path import CubicBezier

from tvarometr_geometry.path_generator import (
    _segment_points,
    generate_path,
    generate_trajectories,
)


@pytest.mark.parametrize("text", list("áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"))
def test_czech_letters_and_decomposed_unicode(text):
    points = generate_path(text)
    assert points
    assert points == generate_path(unicodedata.normalize("NFD", text))
    assert points[0][2] == points[-1][2] == 0.020
    assert any(z == 0 for _, _, z in points)


def test_unsupported_character_is_not_silently_dropped():
    with pytest.raises(ValueError, match="U\\+1F600"):
        generate_path("Věk 😀")


def test_empty_text_has_no_motion():
    assert generate_path("  \n\n ") == []


def test_text_outputs_metres_with_mm_inputs():
    points = generate_path("A", letter_height=680, pen_up=35)
    # A's crossbar starts at font coordinates (155, 213); cap-height is 680.
    assert points[0] == pytest.approx((0.155, 0.213, 0.035))
    assert max(y for _, y, _ in points) == pytest.approx(0.675)


def test_all_paths_and_bounds_use_metres():
    paths = generate_trajectories("32\nmuž\nšťastný", values_width=600, pen_up=35)
    assert paths["units"] == "m"
    left, _, right, _ = paths["values_bounds"]
    assert right - left == pytest.approx(0.6)
    for name in ("labels", "values", "erase"):
        assert paths[name][0][2] == paths[name][-1][2] == pytest.approx(0.035)


def test_line_spacing_and_leading_spaces_preserve_layout():
    line = generate_path("A", 60, 10)
    two_lines = generate_path("A\n\nA", 60, 10)
    assert two_lines[: len(line)] == line
    for actual, (x, y, z) in zip(two_lines[len(line) :], line):
        assert actual == pytest.approx((x, y - 0.180, z))
    spaced = generate_path("  A", 60, 10)
    offsets = [b[0] - a[0] for a, b in zip(line, spaced)]
    assert min(offsets) > 0
    assert offsets == pytest.approx([offsets[0]] * len(line))


def test_pen_lifts_between_disconnected_strokes_and_characters():
    # The font's A has a separate crossbar and two connected diagonal legs.
    single = generate_path("A")
    assert sum(a[2] > 0 and b[2] == 0 for a, b in itertools.pairwise(single)) == 2
    points = generate_path("A A\nč", max_segment_length=15)
    for start, end in itertools.pairwise(points):
        if start[2] != end[2]:
            assert start[:2] == end[:2]  # Lift/lower vertically at the stroke.
        elif start[2] == 0:
            assert math.dist(start, end) <= 0.015 + 1e-9


@pytest.mark.parametrize("max_length", [7, None])
def test_cubic_sampling_respects_error_and_segment_length(max_length):
    # A reversing curve defeats sampling that checks only the midpoint.
    curve = CubicBezier(0j, 300 + 400j, -300 - 400j, 1 + 0j)
    points = [curve.start, *_segment_points(curve, 1, max_length, 0.02)]
    intervals = len(points) - 1
    for i, (start, end) in enumerate(itertools.pairwise(points)):
        if max_length is not None:
            assert abs(end - start) <= max_length + 1e-9
        for fraction in (0.1, 0.25, 0.5, 0.75, 0.9):
            actual = curve.point((i + fraction) / intervals)
            interpolated = start + (end - start) * fraction
            assert abs(actual - interpolated) <= 0.02 + 1e-9


@pytest.mark.parametrize(
    "parameter",
    [
        "letter_height",
        "line_spacing",
        "space_factor",
        "pen_up",
        "max_segment_length",
        "curve_tolerance",
    ],
)
@pytest.mark.parametrize("value", [0, -1, math.nan, math.inf])
def test_invalid_geometry_is_rejected(parameter, value):
    with pytest.raises(ValueError, match=parameter):
        generate_path("A", **{parameter: value})


def test_all_paths_have_fixed_layout_independent_of_values():
    long_text = generate_trajectories("100\nžena\nznechucená", max_segment_length=15)
    short_text = generate_trajectories("8\nmuž\nklidný", max_segment_length=15)
    assert long_text.keys() == {"units", "labels", "values", "erase", "values_bounds"}
    for key in ("labels", "erase", "values_bounds"):
        assert long_text[key] == short_text[key]
    assert long_text["values"] != short_text["values"]
    for key in ("labels", "values", "erase"):
        points = long_text[key]
        assert points[0][2] == points[-1][2] == 0.020
        for a, b in itertools.pairwise(points):
            if a[2] == b[2] == 0:
                assert math.dist(a, b) <= 0.015 + 1e-9


def test_eraser_covers_values_and_its_full_width_clears_labels():
    diameter = 0.036
    paths = generate_trajectories("42\nžena\nšťastná", eraser_width=36)
    left, bottom, right, top = paths["values_bounds"]
    label_right = max(x for x, _, _ in paths["labels"])
    assert min(x for x, _, _ in paths["erase"]) - diameter / 2 > label_right
    assert all(left <= x <= right and bottom <= y <= top for x, y, _ in paths["values"])
    # Horizontal strokes reach both sides; their overlapping footprints span
    # every Y in the fixed rectangle, including corners and empty old text.
    rows = {}
    for x, y, z in paths["erase"]:
        if z == 0:
            rows.setdefault(y, []).append(x)
    sweep_y = sorted(
        y for y, xs in rows.items() if min(xs) == left and max(xs) == right
    )
    assert sweep_y[0] == pytest.approx(bottom)
    assert sweep_y[-1] == pytest.approx(top)
    assert all(b - a <= diameter / 2 + 1e-9 for a, b in itertools.pairwise(sweep_y))


def test_empty_values_still_erase_entire_previous_region():
    empty = generate_trajectories("\n\n")
    assert empty["values"] == []
    assert empty["erase"] == generate_trajectories("35\nmuž\nšťastný")["erase"]


def test_default_example_uses_hundreds_of_points_and_keeps_erase_turns():
    paths = generate_trajectories("32\nmuž\nšťastný")
    assert sum(len(paths[name]) for name in ("labels", "values", "erase")) < 800
    assert len(paths["erase"]) < 100
    left, _, right, _ = paths["values_bounds"]
    contact = [point for point in paths["erase"] if point[2] == 0]
    assert all(x in (left, right) for x, _, _ in contact)
    for a, b in itertools.pairwise(contact):
        assert a[0] == b[0] or a[1] == b[1]  # No diagonals cutting raster turns.


def test_sparse_text_preserves_stroke_endpoints_and_lifts():
    text = "A čůďň"
    sparse = generate_path(text)
    dense = generate_path(text, max_segment_length=15, curve_tolerance=0.1)
    assert len(sparse) < len(dense)
    assert [p for p in sparse if p[2] > 0] == [p for p in dense if p[2] > 0]


def test_text_outside_fixed_area_is_rejected():
    with pytest.raises(ValueError, match="fixed writing area"):
        generate_trajectories("32\nmuž\n" + "velmi dlouhý text" * 5, values_width=20)


def test_wrong_number_of_values_is_rejected():
    with pytest.raises(ValueError, match="three lines"):
        generate_trajectories("Věk: 32")


def test_cli_exports_csv_and_all_paths_json(tmp_path):
    script = Path(__file__).parents[1] / "tvarometr_geometry" / "path_generator.py"
    csv_file = tmp_path / "text.csv"
    subprocess.run(
        [sys.executable, str(script), "Věk: 32", "60", "10", str(csv_file)], check=True
    )
    with csv_file.open() as stream:
        points = [tuple(map(float, row)) for row in csv.reader(stream)]
    assert points == generate_path("Věk: 32", 60, 10)
    json_file = tmp_path / "all.json"
    subprocess.run(
        [
            sys.executable,
            str(script),
            r"32\nmuž\nšťastný",
            "60",
            "10",
            str(json_file),
            "--all-paths",
            "--space-factor",
            "1.3",
        ],
        check=True,
    )
    assert json.loads(json_file.read_text()) == json.loads(
        json.dumps(generate_trajectories("32\nmuž\nšťastný"))
    )
