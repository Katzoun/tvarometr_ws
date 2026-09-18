"""Which person in the frame is the visitor, and whether their face is in view.

A face's height in pixels says how far somebody is whatever their size; a body's
width cannot tell a child close up from an adult far away. So faces decide when
one is in view and bodies only when none is. A visitor with no face still counts.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Visitor:
    person: int | None  # into the person boxes, None when nobody is close enough
    face: int | None  # into the face boxes, None when their face is not in view
    by_face: bool  # whether face height decided, rather than body width
    too_far: tuple[int, ...]  # people the deciding rule rejected as too far away
    ambiguous: bool  # the runner-up scores nearly as high - worth a warning
    weights: tuple[float, ...]  # axis weight per person, 1.0 on the axis


def box_width(box):
    return box[2] - box[0]


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


def select_visitor(
    persons,
    faces,
    face_of_person,
    image_width,
    min_face_height_px,
    min_person_width_px,
    ambiguity_ratio,
    axis_x=0.5,
    axis_falloff=0.0,
):
    """Pick the nearest face, or the widest body while no face is tall enough.

    `face_of_person` maps a person's index to their face's; whichever rule decides,
    the winner is its measure times the axis weight, and the other people are too far.
    """
    people = range(len(persons))
    weights = tuple(axis_weight(b, image_width, axis_x, axis_falloff) for b in persons)

    def face_height(i):
        face = face_of_person.get(i)
        return box_height(faces[face]) if face is not None else 0

    by_face = any(face_height(i) >= min_face_height_px for i in people)
    minimum = min_face_height_px if by_face else min_person_width_px

    def size(i):
        return face_height(i) if by_face else box_width(persons[i])

    def score(i):
        return size(i) * weights[i]

    too_far = tuple(i for i in people if size(i) < minimum)
    candidates = sorted(
        (i for i in people if i not in too_far), key=score, reverse=True
    )
    if not candidates:
        return Visitor(None, None, by_face, too_far, ambiguous=False, weights=weights)

    best = candidates[0]
    ambiguous = len(candidates) > 1 and score(candidates[1]) >= ambiguity_ratio * score(
        best
    )
    return Visitor(
        best, face_of_person.get(best), by_face, too_far, ambiguous, weights
    )
