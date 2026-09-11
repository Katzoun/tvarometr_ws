"""Text to single-line drawing trajectories, independent of ROS and the robot.

Coordinates are millimetres: X goes right, Y up, Z=0 touches the board.
The first line's baseline is Y=0; subsequent lines run down the board.
Relief SingleLine includes Czech accents, which may exceed letter_height.
Each disconnected stroke starts and ends with the pen lifted.
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
            math.ceil(speed / max_segment_length),
            math.ceil(math.sqrt(acceleration / (8 * curve_tolerance))),
        )
    elif isinstance(segment, (Line, Close)):
        steps = max(
            1, math.ceil(abs(segment.end - segment.start) * scale / max_segment_length)
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
    max_segment_length: float = 15.0,
    curve_tolerance: float = 0.1,
) -> list[tuple[float, float, float]]:
    """Return (x, y, z) waypoints, with the existing drawing-node call signature.

    letter_height scales the font's nominal capital height (680 font units).
    letter_spacing adds tracking to the font's own advance widths. Spaces use
    the font's space advance multiplied by space_factor, plus letter_spacing.
    line_spacing is baseline separation as a multiple of letter_height.
    max_segment_length limits pen-down steps; curve_tolerance bounds their
    deviation from the Bezier curves, both in mm. Travel moves are lifted.
    NFC normalization accepts both composed and decomposed Czech characters.
    Unsupported characters raise ValueError instead of silently losing text.

    The function has no cycle state: callers choose which text to draw.
    """
    for name, value in (
        ("letter_height", letter_height),
        ("space_factor", space_factor),
        ("line_spacing", line_spacing),
        ("pen_up", pen_up),
        ("max_segment_length", max_segment_length),
        ("curve_tolerance", curve_tolerance),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if not math.isfinite(letter_spacing) or letter_spacing < 0:
        raise ValueError("letter_spacing must be finite and nonnegative")

    text = unicodedata.normalize(
        "NFC", input_str.replace("\r\n", "\n").replace("\r", "\n")
    )
    cap_height, glyphs = _load_font()
    missing = sorted(set(text) - glyphs.keys() - {"\n"})
    if missing:
        names = ", ".join(f"{ch!r} (U+{ord(ch):04X})" for ch in missing)
        raise ValueError(f"Characters missing from Relief SingleLine: {names}")

    scale = letter_height / cap_height
    points = []
    pen_down = False

    def lift():
        nonlocal pen_down
        if pen_down:
            x, y, _ = points[-1]
            points.append((x, y, pen_up))
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
                    x, y = start.real + x_offset, start.imag + y_offset
                    points.extend([(x, y, pen_up), (x, y, 0.0)])
                    pen_down = True
                for point in _segment_points(
                    segment, scale, max_segment_length, curve_tolerance
                ):
                    points.append((point.real + x_offset, point.imag + y_offset, 0.0))
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
    max_segment_length: float = 15.0,
    curve_tolerance: float = 0.1,
) -> dict:
    """Return labels, values and erase paths together, plus values_bounds.

    input_str contains exactly three lines: age, gender, mood (values only).
    Paths share a board coordinate system and use the active tool's contact
    plane as Z=0. This only generates geometry; it does not change tools or
    track whether a robot has successfully drawn the labels.

    First cycle: draw labels + values. Later cycles: erase, then draw values.
    Keep layout parameters constant across cycles. The erase region depends
    on the font bounds and values_width, never on the current text length.
    Text outside that region is rejected. eraser_width is the effective
    circular footprint diameter; overlapping sweeps cover the whole region.
    label_gap is clearance between label ink and the eraser's swept footprint.
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
    left = max(p[0] for p in labels) + curve_tolerance + label_gap + eraser_width / 2
    right = left + values_width
    # Use the entire bundled font's vertical bounds, including diacritics and
    # descenders, so previous values are erased even when new ones are shorter.
    font_file = Path(__file__).with_name("fonts") / "ReliefSingleLineSVG-Regular.svg"
    face = ET.parse(font_file).find(".//{*}font-face")
    if face is None:
        raise ValueError("SVG is missing the font-face element")
    _, min_y, _, max_y = map(float, face.attrib["bbox"].split())
    scale = letter_height / float(face.attrib["cap-height"])
    bottom = min_y * scale - 2 * letter_height * line_spacing
    top = max_y * scale
    value_points = [(x + left, y, z) for x, y, z in value_points]
    if any(not (left <= x <= right and bottom <= y <= top) for x, y, _ in value_points):
        raise ValueError(
            "Values exceed the fixed writing area; increase values_width or reduce letter_height"
        )

    rows = max(1, math.ceil((top - bottom) / (eraser_width / 2)))
    corners = []
    for row in range(rows + 1):
        y = top - (top - bottom) * row / rows
        start, end = (left, right) if row % 2 == 0 else (right, left)
        corners.extend([(start, y), (end, y)])
    erase = [(left, top, pen_up), (left, top, 0.0)]
    for (x0, y0), (x1, y1) in itertools.pairwise(corners):
        steps = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / max_segment_length))
        erase.extend(
            (x0 + (x1 - x0) * step / steps, y0 + (y1 - y0) * step / steps, 0.0)
            for step in range(1, steps)
        )
        erase.append((x1, y1, 0.0))
    erase.append((*corners[-1], pen_up))
    return {
        "labels": labels,
        "values": value_points,
        "erase": erase,
        "values_bounds": [left, bottom, right, top],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Text to XYZ trajectories in mm (CSV or JSON)"
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
    parser.add_argument("--max-segment-length", type=float, default=15.0)
    parser.add_argument("--curve-tolerance", type=float, default=0.1)
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
        if args.all_paths:
            json.dump(result, output, ensure_ascii=False, indent=2)
        else:
            csv.writer(output).writerows(result)
    print(f"Saved '{args.output}'.")


if __name__ == "__main__":
    main()
