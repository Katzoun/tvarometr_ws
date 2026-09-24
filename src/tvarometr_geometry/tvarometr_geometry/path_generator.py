"""Text to single-line drawing trajectories, independent of ROS and the robot.

Lengths in are mm, coordinates out metres: X right, Y up, Z=0 on the board.
"""

import argparse
import csv
import itertools
import json
import math
import unicodedata
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from svg.path import Close, CubicBezier, Line, Move, parse_path

MM_TO_M = 0.001


@lru_cache(maxsize=1)
def _load_font():
    font_file = Path(__file__).with_name("fonts") / "ReliefSingleLineSVG-Regular.svg"
    font = ET.parse(font_file).find(".//{*}font")
    if font is None:
        raise ValueError("SVG is missing the font element")
    face = font.find("{*}font-face")
    if face is None:
        raise ValueError("SVG is missing the font-face element")
    cap_height = float(face.attrib["cap-height"])
    default_advance = font.attrib["horiz-adv-x"]
    glyphs = {
        glyph.attrib["unicode"]: (
            parse_path(glyph.get("d", "")),
            float(glyph.get("horiz-adv-x", default_advance)),
        )
        for glyph in font.findall("{*}glyph")
        if glyph.get("unicode") is not None
    }
    return cap_height, glyphs


def _line_steps(length, max_segment_length):
    if max_segment_length is None:
        return 1
    ratio = length / max_segment_length
    nearest = round(ratio)
    # Unit conversion can turn exactly 40 steps into 40.00000000000001.
    if math.isclose(ratio, nearest, rel_tol=0, abs_tol=1e-12):
        return max(1, nearest)
    return max(1, math.ceil(ratio))


def _segment_points(segment, scale, max_segment_length, curve_tolerance):
    """Sample with bounds on chord length and cubic interpolation error."""
    if isinstance(segment, CubicBezier):
        p0, p1, p2, p3 = (
            segment.start,
            segment.control1,
            segment.control2,
            segment.end,
        )
        # Bounds on first and second derivatives for t in [0, 1].
        speed = 3 * max(abs(p1 - p0), abs(p2 - p1), abs(p3 - p2)) * scale
        acceleration = 6 * max(abs(p2 - 2 * p1 + p0), abs(p3 - 2 * p2 + p1)) * scale
        steps = max(
            1,
            _line_steps(speed, max_segment_length),
            math.ceil(math.sqrt(acceleration / (8 * curve_tolerance))),
        )
    elif isinstance(segment, (Line, Close)):
        steps = _line_steps(
            abs(segment.end - segment.start) * scale, max_segment_length
        )
    else:
        raise TypeError(f"Unsupported font segment: {type(segment).__name__}")
    return (segment.point(i / steps) * scale for i in range(1, steps + 1))


def generate_path(
    input_str: str,
    letter_height: float = 80.0,
    letter_spacing: float = 20.0,
    space_factor: float = 2.0,
    line_spacing: float = 1.5,
    *,
    pen_up: float = 20.0,
    max_segment_length: float | None = None,
    curve_tolerance: float = 0.5,
) -> list[tuple[float, float, float]]:
    """Return (x, y, z) waypoints in metres; input lengths are mm.

    letter_height is the capital height, line_spacing a multiple of it, and
    curve_tolerance the Bezier error. Unsupported characters raise ValueError.
    """
    for name, value in (
        ("letter_height", letter_height),
        ("space_factor", space_factor),
        ("line_spacing", line_spacing),
        ("pen_up", pen_up),
        ("curve_tolerance", curve_tolerance),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if not math.isfinite(letter_spacing) or letter_spacing < 0:
        raise ValueError("letter_spacing must be finite and nonnegative")
    if max_segment_length is not None and (
        not math.isfinite(max_segment_length) or max_segment_length <= 0
    ):
        raise ValueError("max_segment_length must be None or finite and positive")

    text = unicodedata.normalize(
        "NFC", input_str.replace("\r\n", "\n").replace("\r", "\n")
    )
    cap_height, glyphs = _load_font()
    missing = sorted(set(text) - glyphs.keys() - {"\n"})
    if missing:
        names = ", ".join(f"{ch!r} (U+{ord(ch):04X})" for ch in missing)
        raise ValueError(f"Characters missing from Relief SingleLine: {names}")

    scale = letter_height / cap_height
    pen_up_m = pen_up * MM_TO_M
    points = []
    pen_down = False

    def lift():
        nonlocal pen_down
        if pen_down:
            x, y, _ = points[-1]
            points.append((x, y, pen_up_m))
            pen_down = False

    for row, line in enumerate(text.split("\n")):
        x_offset = 0.0
        y_offset = -row * letter_height * line_spacing
        for character in line:
            path, advance = glyphs[character]
            for segment in path:
                if isinstance(segment, Move):
                    lift()
                    continue
                if not pen_down:
                    start = segment.start * scale
                    x = (start.real + x_offset) * MM_TO_M
                    y = (start.imag + y_offset) * MM_TO_M
                    points.extend([(x, y, pen_up_m), (x, y, 0.0)])
                    pen_down = True
                for point in _segment_points(
                    segment, scale, max_segment_length, curve_tolerance
                ):
                    points.append(
                        (
                            (point.real + x_offset) * MM_TO_M,
                            (point.imag + y_offset) * MM_TO_M,
                            0.0,
                        )
                    )
            lift()
            x_offset += (
                advance * scale * (space_factor if character == " " else 1)
                + letter_spacing
            )
    return points


def generate_trajectories(
    input_str: str,
    letter_height: float = 60.0,
    letter_spacing: float = 10.0,
    space_factor: float = 1.3,
    line_spacing: float = 1.5,
    *,
    values_width: float = 600.0,
    eraser_width: float = 20.0,
    label_gap: float = 10.0,
    pen_up: float = 20.0,
    max_segment_length: float | None = None,
    curve_tolerance: float = 0.5,
) -> dict:
    """Return label, value and erase paths in metres; input lengths are mm.

    input_str is three lines: age, gender, mood. The erase region depends only on
    the font and values_width; eraser_width is the footprint diameter.
    """
    values = input_str.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(values) != 3:
        raise ValueError("Expected three lines of values: age, gender, mood")
    for name, value in (
        ("values_width", values_width),
        ("eraser_width", eraser_width),
        ("label_gap", label_gap),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    options = {
        "letter_height": letter_height,
        "letter_spacing": letter_spacing,
        "space_factor": space_factor,
        "line_spacing": line_spacing,
        "pen_up": pen_up,
        "max_segment_length": max_segment_length,
        "curve_tolerance": curve_tolerance,
    }
    labels = generate_path("Věk:\nPohlaví:\nNálada:", **options)
    value_points = generate_path("\n".join(values), **options)
    # Include curve sampling error in the clearance to the permanent ink.
    left = (
        max(p[0] for p in labels)
        + (curve_tolerance + label_gap + eraser_width / 2) * MM_TO_M
    )
    limit = left + values_width * MM_TO_M
    # Use the entire bundled font's vertical bounds, including diacritics and
    # descenders, so previous values are erased even when new ones are shorter.
    font_file = Path(__file__).with_name("fonts") / "ReliefSingleLineSVG-Regular.svg"
    face = ET.parse(font_file).find(".//{*}font-face")
    if face is None:
        raise ValueError("SVG is missing the font-face element")
    _, min_y, _, max_y = map(float, face.attrib["bbox"].split())
    scale = letter_height / float(face.attrib["cap-height"]) * MM_TO_M
    bottom = min_y * scale - 2 * letter_height * line_spacing * MM_TO_M
    top = max_y * scale
    value_points = [(x + left, y, z) for x, y, z in value_points]
    if any(not (left <= x <= limit and bottom <= y <= top) for x, y, _ in value_points):
        raise ValueError(
            "Values exceed the fixed writing area; increase values_width or reduce letter_height"
        )
    # The sweep ends at the last of the ink, so a short value does not drag the
    # eraser over empty board. With nothing written it clears the whole column,
    # the only way left to reach what an earlier run put there.
    right = (
        min(max(p[0] for p in value_points) + curve_tolerance * MM_TO_M, limit)
        if value_points
        else limit
    )

    rows = max(1, math.ceil((top - bottom) / (eraser_width * MM_TO_M / 2)))
    corners = []
    for row in range(rows + 1):
        y = top - (top - bottom) * row / rows
        start, end = (left, right) if row % 2 == 0 else (right, left)
        corners.extend([(start, y), (end, y)])
    pen_up_m = pen_up * MM_TO_M
    max_segment_m = None if max_segment_length is None else max_segment_length * MM_TO_M
    erase = [(left, top, pen_up_m), (left, top, 0.0)]
    for (x0, y0), (x1, y1) in itertools.pairwise(corners):
        steps = _line_steps(math.hypot(x1 - x0, y1 - y0), max_segment_m)
        erase.extend(
            (x0 + (x1 - x0) * step / steps, y0 + (y1 - y0) * step / steps, 0.0)
            for step in range(1, steps)
        )
        erase.append((x1, y1, 0.0))
    erase.append((*corners[-1], pen_up_m))
    # The whole sweep runs twice. Between the passes the eraser rides back over
    # the first corner at pen_up, so it touches nothing on the way.
    erase = erase * 2
    return {
        "units": "m",
        "labels": labels,
        "values": value_points,
        "erase": erase,
        "values_bounds": [left, bottom, right, top],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Text to XYZ trajectories in metres (CSV or JSON); input lengths in mm"
    )
    parser.add_argument("text", help=r"Text; \n starts a new line")
    parser.add_argument(
        "height", type=float, help="Capital height, excluding accents (mm)"
    )
    parser.add_argument("spacing", type=float, help="Extra character spacing (mm)")
    parser.add_argument(
        "output", type=Path, help="Output CSV, or JSON with --all-paths"
    )
    parser.add_argument("--line-spacing", type=float, default=1.5)
    parser.add_argument("--space-factor", type=float, default=2.0)
    parser.add_argument("--pen-up", type=float, default=20.0)
    parser.add_argument(
        "--max-segment-length",
        type=float,
        help="Optional contact segment length limit (mm); default: endpoints on straight lines",
    )
    parser.add_argument(
        "--curve-tolerance",
        type=float,
        default=0.5,
        help="Maximum curve approximation error (mm; default: 0.5)",
    )
    parser.add_argument(
        "--all-paths",
        action="store_true",
        help="Three input lines: age, gender, mood; export all paths as JSON",
    )
    parser.add_argument(
        "--values-width", type=float, default=600.0, help="Values area width (mm)"
    )
    parser.add_argument(
        "--eraser-width",
        type=float,
        default=20.0,
        help="Effective eraser diameter (mm)",
    )
    parser.add_argument(
        "--label-gap",
        type=float,
        default=10.0,
        help="Label clearance from eraser footprint (mm)",
    )
    args = parser.parse_args()
    try:
        generator = generate_trajectories if args.all_paths else generate_path
        layout = (
            {
                "values_width": args.values_width,
                "eraser_width": args.eraser_width,
                "label_gap": args.label_gap,
            }
            if args.all_paths
            else {}
        )
        result = generator(
            args.text.replace("\\n", "\n"),
            args.height,
            args.spacing,
            space_factor=args.space_factor,
            line_spacing=args.line_spacing,
            pen_up=args.pen_up,
            max_segment_length=args.max_segment_length,
            curve_tolerance=args.curve_tolerance,
            **layout,
        )
    except ValueError as error:
        parser.error(str(error))
    with args.output.open("w", encoding="utf-8", newline="") as output:
        if isinstance(result, dict):
            json.dump(result, output, ensure_ascii=False, indent=2)
        else:
            csv.writer(output).writerows(result)
    print(f"Saved '{args.output}'.")
    if isinstance(result, dict):
        print(
            "Points: "
            + ", ".join(
                f"{name}={len(result[name])}" for name in ("labels", "values", "erase")
            )
        )
    else:
        print(f"Points: {len(result)}")


if __name__ == "__main__":
    main()
