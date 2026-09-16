"""Draws what the node saw onto the frame: labelled for debugging, plain for the TV."""

import cv2

SELECTED = (0, 200, 0)  # BGR
TOO_FAR = (0, 0, 220)
OTHER = (170, 170, 170)
AXIS = (0, 220, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _label(image, text, x, y, colour, scale):
    thickness = max(1, round(2 * scale))
    (width, height), baseline = cv2.getTextSize(text, FONT, scale, thickness)
    y = max(y, height + baseline)
    cv2.rectangle(
        image, (x, y - height - baseline), (x + width + 6, y), colour, cv2.FILLED
    )
    cv2.putText(image, text, (x + 3, y - baseline), FONT, scale, (0, 0, 0), thickness)


def _box(image, box, colour, thickness):
    x1, y1, x2, y2 = box
    cv2.rectangle(image, (x1, y1), (x2, y2), colour, max(1, thickness))


def _dashed_vertical(image, x, colour, thickness, dash):
    for y in range(0, image.shape[0], 2 * dash):
        cv2.line(image, (x, y), (x, y + dash), colour, thickness)


def draw_axis(image, axis_x, axis_falloff, scale):
    """The selection axis, and dashed lines where a person counts half."""
    height, width = image.shape[:2]
    x = round(axis_x * width)
    cv2.line(image, (x, 0), (x, height), AXIS, max(1, round(3 * scale)))
    if axis_falloff > 0:
        for side in (-1, 1):
            xs = round((axis_x + side * axis_falloff) * width)
            if 0 <= xs < width:
                _dashed_vertical(
                    image, xs, AXIS, max(1, round(scale)), round(20 * scale)
                )


def draw_scene(image, persons, faces, visitor):
    """A copy of `image` with plain boxes, the visitor's in green - for the TV."""
    out = image.copy()
    scale = out.shape[0] / 1080
    for i, box in enumerate(persons):
        colour = SELECTED if i == visitor.person else OTHER
        _box(out, box, colour, round((6 if i == visitor.person else 3) * scale))
    if visitor.face is not None:
        _box(out, faces[visitor.face], SELECTED, round(6 * scale))
    return out


def draw_debug(image, persons, faces, labels, visitor, status, axis_x, axis_falloff):
    """A copy of `image` with the axis, everyone boxed and the visitor labelled."""
    out = image.copy()
    scale = out.shape[0] / 1080  # text that stays readable at any resolution
    draw_axis(out, axis_x, axis_falloff, scale)

    for i, box in enumerate(persons):
        if i == visitor.person:
            colour, thickness = SELECTED, 4
        elif i in visitor.too_far:
            colour, thickness = TOO_FAR, 2
        else:
            colour, thickness = OTHER, 2
        _box(out, box, colour, round(thickness * scale))
        _label(out, labels[i], box[0], box[1] - 4, colour, 0.8 * scale)

    for i, box in enumerate(faces):
        _box(out, box, SELECTED if i == visitor.face else OTHER, round(2 * scale))

    _label(out, status, 10, round(40 * scale), (255, 255, 255), scale)
    return out
