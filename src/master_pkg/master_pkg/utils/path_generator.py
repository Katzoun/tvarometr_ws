import math
from HersheyFonts import HersheyFonts

def generate_path(input_str: str, letter_height: float = 80.0, letter_spacing: float = 20, space_factor: float = 2.0):

    max_segment_length = 15
    font = HersheyFonts()
    font.load_default_font()
    font.normalize_rendering(letter_height)

    # Získání úseček a rozměrů pro každé písmeno
    glyphs = []
    for ch in input_str:
        if ch == ' ':
            space_width = letter_spacing * space_factor
            glyphs.append({'char': ' ', 'lines': [], 'min_x': 0.0, 'max_x': space_width})
        else:
            lines = list(font.lines_for_text(ch))
            if not lines:
                print(f"Upozornění: Znak '{ch}' není ve fontu, přeskočeno.")
                glyphs.append({'char': ch, 'lines': [], 'min_x': 0.0, 'max_x': 0.0})
                continue
            min_x = min(min(x1, x2) for (x1, y1), (x2, y2) in lines)
            max_x = max(max(x1, x2) for (x1, y1), (x2, y2) in lines)
            glyphs.append({'char': ch, 'lines': lines, 'min_x': min_x, 'max_x': max_x})

    # SPRÁVNÝ výpočet posunů jednotlivých písmen na ose X
    offsets = []
    for i, glyph in enumerate(glyphs):
        if i == 0:
            offset = -glyph['min_x']
        else:
            prev = glyphs[i-1]
            offset = offsets[-1] + (prev['max_x'] - prev['min_x']) + letter_spacing
        offsets.append(offset)

    # Sestavení spojité dráhy bod po bodu
    path_points = []
    pen_down = False
    last_point = None
    for glyph, offset in zip(glyphs, offsets):
        if glyph['char'] == ' ':
            continue
        for ((x1, y1), (x2, y2)) in glyph['lines']:
            x1 += offset
            x2 += offset
            start_point = (x1, y1)
            end_point   = (x2, y2)
            if last_point is None or (start_point != last_point) or not pen_down:
                if last_point is not None and pen_down:
                    path_points.append((last_point[0], last_point[1], 20.0))  # pen up to 20
                    pen_down = False
                path_points.append((x1, y1, 20.0))  # pen up to 20
                path_points.append((x1, y1, 0.0))
                pen_down = True
            dx = x2 - x1
            dy = y2 - y1
            segment_length = math.hypot(dx, dy)
            steps = max(1, int(segment_length / max_segment_length))
            for j in range(1, steps+1):
                t = j / steps
                x = x1 + t * dx
                y = y1 + t * dy
                z = 0.0
                path_points.append((x, y, z))
            last_point = end_point
    if last_point is not None and pen_down:
        path_points.append((last_point[0], last_point[1], 20.0))  # pen up to 20
    return path_points

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generuje CSV soubor se souřadnicemi dráhy pro zadaný text.")
    parser.add_argument("text", help="Text (slovo), které se má vykreslit")
    parser.add_argument("height", type=float, help="Výška písma (mm)")
    parser.add_argument("spacing", type=float, help="Mezera mezi písmeny (mm)")
    parser.add_argument("output", help="Výstupní CSV soubor")
    args = parser.parse_args()

    points = generate_path(args.text, args.height, args.spacing)
    with open(args.output, "w") as f:
        for (x, y, z) in points:
            f.write(f"{x:.3f},{y:.3f},{z:.3f}\n")
    print(f"CSV soubor '{args.output}' byl úspěšně vytvořen s {len(points)} body.")

