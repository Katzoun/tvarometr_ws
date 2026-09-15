"""Which of the detected faces belongs to the visitor.

The visitor stands closest to the camera, so theirs is the tallest face, and near
the vertical axis where visitors are expected to stand. Height rather than area,
because a turned head narrows the box but barely shortens it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    index: int | None  # into the boxes given, None when nobody qualifies
    too_small: tuple[int, ...]  # faces rejected as too far away
    ambiguous: bool  # the runner-up scores nearly as high - worth a warning
    weights: tuple[float, ...]  # axis weight per box, 1.0 on the axis


def box_height(box):
    return box[3] - box[1]


def axis_weight(box, image_width, axis_x, axis_falloff):
    """1 on the axis, a half at `axis_falloff` from it; both fractions of the width.

    A falloff of 0 or less turns the weighting off.
    """
    if axis_falloff <= 0 or image_width <= 0:
        return 1.0
    distance = abs((box[0] + box[2]) / 2 / image_width - axis_x)
    return 0.5 ** ((distance / axis_falloff) ** 2)


def select_nearest_face(
    boxes, image_width, min_height_px, ambiguity_ratio, axis_x=0.5, axis_falloff=0.0
):
    """Pick the face with the best height times axis weight; boxes are (x1, y1, x2, y2).

    Faces shorter than `min_height_px` are too far from the camera to count,
    wherever they stand.
    """
    weights = tuple(axis_weight(b, image_width, axis_x, axis_falloff) for b in boxes)
    too_small = tuple(
        i for i, box in enumerate(boxes) if box_height(box) < min_height_px
    )

    def score(i):
        return box_height(boxes[i]) * weights[i]

    candidates = sorted(
        (i for i in range(len(boxes)) if i not in too_small), key=score, reverse=True
    )
    if not candidates:
        return Selection(None, too_small, ambiguous=False, weights=weights)

    best = candidates[0]
    ambiguous = len(candidates) > 1 and score(candidates[1]) >= ambiguity_ratio * score(
        best
    )
    return Selection(best, too_small, ambiguous, weights)
