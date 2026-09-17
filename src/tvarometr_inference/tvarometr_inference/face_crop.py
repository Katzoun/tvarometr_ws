"""The part of the frame the emotion model sees.

Same geometry as `benchmark/run_model.py --crop square`, so its numbers carry over.
"""


def emotion_crop(box, margin, image_size):
    """A square around the face box, grown by `margin` of its side on each side.

    `image_size` is (width, height); near an edge the clamped crop stops being square.
    """
    width, height = image_size
    x1, y1, x2, y2 = box
    side = max(x2 - x1, y2 - y1) * (1 + 2 * margin)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return (
        max(round(cx - side / 2), 0),
        max(round(cy - side / 2), 0),
        min(round(cx + side / 2), width),
        min(round(cy + side / 2), height),
    )
