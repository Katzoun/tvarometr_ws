import math
from HersheyFonts import HersheyFonts

def generate_path(input_str: str, letter_height: float = 80.0, letter_spacing: float = 20, space_factor: float = 2.0, line_spacing: float = 1.5):

    max_segment_length = 15
    font = HersheyFonts()
    font.load_default_font()
    font.normalize_rendering(letter_height)

    # Rozdělení textu na řádky
    lines_text = input_str.split('\n')
    
    # Zpracování všech řádků
    all_glyphs = []
    all_offsets = []
    
    for line_idx, line_text in enumerate(lines_text):
        # Získání úseček a rozměrů pro každé písmeno v řádku
        line_glyphs = []
        for ch in line_text:
            if ch == ' ':
                space_width = letter_spacing * space_factor
                line_glyphs.append({'char': ' ', 'lines': [], 'min_x': 0.0, 'max_x': space_width})
            else:
                lines = list(font.lines_for_text(ch))
                if not lines:
                    print(f"Upozornění: Znak '{ch}' není ve fontu, přeskočeno.")
                    line_glyphs.append({'char': ch, 'lines': [], 'min_x': 0.0, 'max_x': 0.0})
                    continue
                min_x = min(min(x1, x2) for (x1, y1), (x2, y2) in lines)
                max_x = max(max(x1, x2) for (x1, y1), (x2, y2) in lines)
                line_glyphs.append({'char': ch, 'lines': lines, 'min_x': min_x, 'max_x': max_x})

        # Výpočet posunů pro písma v řádku
        line_offsets = []
        for i, glyph in enumerate(line_glyphs):
            if i == 0:
                offset = -glyph['min_x']
            else:
                prev = line_glyphs[i-1]
                offset = line_offsets[-1] + (prev['max_x'] - prev['min_x']) + letter_spacing
            line_offsets.append(offset)
        
        # Výpočet Y offsetu pro řádek
        y_offset = -line_idx * letter_height * line_spacing
        
        # Přidání informace o Y offsetu k každému glyfu
        for glyph in line_glyphs:
            glyph['y_offset'] = y_offset
        
        all_glyphs.extend(line_glyphs)
        all_offsets.extend(line_offsets)

    # Sestavení spojité dráhy bod po bodu
    path_points = []
    pen_down = False
    last_point = None
    for glyph, offset in zip(all_glyphs, all_offsets):
        if glyph['char'] == ' ':
            continue
        y_offset = glyph['y_offset']
        for ((x1, y1), (x2, y2)) in glyph['lines']:
            x1 += offset
            x2 += offset
            y1 += y_offset
            y2 += y_offset
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
    parser.add_argument("text", help="Text (slovo), které se má vykreslit (podporuje \\n pro nové řádky)")
    parser.add_argument("height", type=float, help="Výška písma (mm)")
    parser.add_argument("spacing", type=float, help="Mezera mezi písmeny (mm)")
    parser.add_argument("output", help="Výstupní CSV soubor")
    parser.add_argument("--line-spacing", type=float, default=1.5, help="Násobitel pro mezery mezi řádky (výchozí: 1.5)")
    args = parser.parse_args()

    # Nahradíme \\n za skutečné nové řádky
    text = args.text.replace('\\n', '\n')
    
    points = generate_path(text, args.height, args.spacing, line_spacing=args.line_spacing)
    with open(args.output, "w") as f:
        for (x, y, z) in points:
            f.write(f"{x:.3f},{y:.3f},{z:.3f}\n")
    print(f"CSV soubor '{args.output}' byl úspěšně vytvořen s {len(points)} body.")

