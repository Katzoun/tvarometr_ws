"""Where the camera goes next to put the visitor's face at the target height.

A face is about `face_height_m` tall, which turns pixels into metres. With no
face in view the camera steps blindly: towards the top of the body box, or down.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    z: float  # where the camera goes next, in wobj, metres
    error_px: float  # face centre below (+) or above (-) the target
    centred: bool  # close enough already, z is unchanged
    at_limit: bool  # the move was cut short by min_z or max_z


@dataclass(frozen=True)
class Centring:
    """The tuning of the loop, straight from the node's parameters."""

    target_y: float  # where the face centre belongs, as a fraction of the height
    tolerance: float  # how far off that may be, same units
    gain: float  # how much of the error one step corrects
    max_step: float  # metres, the longest single move
    min_z: float
    max_z: float
    face_height_m: float

    def nudge(self, z, direction) -> Step:
        """One blind step, up (+1) or down (-1), for when nobody is in the frame."""
        return self._clamped(z, direction * self.max_step, error_px=0.0)

    def blind_step(self, z, person_top_y, image_height):
        """One step towards the top of the visitor's body box, where their head is.

        None when it is already where a face belongs: the head is turned away.
        """
        error_px = person_top_y - self.target_y * image_height
        if abs(error_px) <= self.tolerance * image_height:
            return None
        return self._clamped(
            z, -self.max_step if error_px > 0 else self.max_step, error_px
        )

    def step(self, z, face_centre_y, face_height_px, image_height) -> Step:
        error_px = face_centre_y - self.target_y * image_height
        if abs(error_px) <= self.tolerance * image_height:
            return Step(z, error_px, centred=True, at_limit=False)

        # Wobj Z points up and image y grows downwards, so the two disagree: a
        # face below the target (error above zero) rises when the camera goes down.
        move = -self.gain * error_px * self.face_height_m / face_height_px
        return self._clamped(z, max(-self.max_step, min(self.max_step, move)), error_px)

    def _clamped(self, z, move, error_px) -> Step:
        wanted = z + move
        return Step(
            z=min(max(wanted, self.min_z), self.max_z),
            error_px=error_px,
            centred=False,
            at_limit=not self.min_z <= wanted <= self.max_z,
        )
