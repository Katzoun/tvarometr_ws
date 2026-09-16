"""Which of the people in the frame is the visitor, and whether we see their face.

The visitor stands closest to the camera, so theirs is the widest person box.
Width and not height, because somebody standing close is cut off by the top or
the bottom of the frame long before they are narrow - a child the camera looks
over, or a tall visitor it sees the chest of. Standing near the axis over the
floor mark counts too.

The face only says where to look, so a visitor without one is still the visitor.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Visitor:
    person: int | None  # into the person boxes, None when nobody is close enough
    face: int | None  # into the face boxes, None when their face is not in view
    too_far: tuple[int, ...]  # people rejected as too far away
    ambiguous: bool  # the runner-up scores nearly as high - worth a warning
    weights: tuple[float, ...]  # axis weight per person, 1.0 on the axis


def box_width(box):
    return box[2] - box[0]


def axis_weight(box, image_width, axis_x, axis_falloff):
    """1 on the axis, a half at `axis_falloff` from it; both fractions of the width.

    A falloff of 0 or less turns the weighting off.
    """
    if axis_falloff <= 0 or image_width <= 0:
        return 1.0
    distance = abs((box[0] + box[2]) / 2 / image_width - axis_x)
    return 0.5 ** ((distance / axis_falloff) ** 2)


def select_visitor(
    persons,
    face_of_person,
    image_width,
    min_width_px,
    ambiguity_ratio,
    axis_x=0.5,
    axis_falloff=0.0,
):
    """Pick the person with the best width times axis weight, and their face.

    `persons` are (x1, y1, x2, y2); `face_of_person` maps a person's index to
    the index of their face. People narrower than `min_width_px` are too far
    from the camera to be the visitor, wherever they stand.
    """
    weights = tuple(axis_weight(b, image_width, axis_x, axis_falloff) for b in persons)
    too_far = tuple(i for i, box in enumerate(persons) if box_width(box) < min_width_px)

    def score(i):
        return box_width(persons[i]) * weights[i]

    candidates = sorted(
        (i for i in range(len(persons)) if i not in too_far), key=score, reverse=True
    )
    if not candidates:
        return Visitor(None, None, too_far, ambiguous=False, weights=weights)

    best = candidates[0]
    ambiguous = len(candidates) > 1 and score(candidates[1]) >= ambiguity_ratio * score(
        best
    )
    return Visitor(best, face_of_person.get(best), too_far, ambiguous, weights)
