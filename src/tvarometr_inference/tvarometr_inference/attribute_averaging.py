"""The models' answers for the visitor's face, averaged over several frames.

One frame can catch a blink or a half-turned head.
"""

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class Sample:
    """The models' answer for the visitor's face in one frame."""

    age: float
    male_probability: float  # 0 is certainly female, 1 certainly male
    emotion_probabilities: tuple[float, ...]  # one per emotion label
    face_bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class Averaged:
    age: float
    gender: str
    emotion: str
    emotion_confidence: float
    face_bbox: tuple[int, int, int, int]  # where the face was in the last frame


def male_probability(gender, gender_score):
    """MiVOLO names the likelier gender and how sure it is; this is P(male)."""
    return gender_score if gender == "male" else 1.0 - gender_score


def average(samples, emotion_labels) -> Averaged:
    """One answer out of several; `samples` must not be empty.

    Age is the median, so one wild guess does not drag it. Gender and emotion
    average probabilities, so a sure frame outweighs a hesitant one.
    """
    count = len(samples)
    emotion = [
        sum(sample.emotion_probabilities[k] for sample in samples) / count
        for k in range(len(emotion_labels))
    ]
    best = max(range(len(emotion)), key=emotion.__getitem__)
    male = sum(sample.male_probability for sample in samples) / count

    return Averaged(
        age=median(sample.age for sample in samples),
        gender="male" if male >= 0.5 else "female",
        emotion=emotion_labels[best],
        emotion_confidence=emotion[best],
        face_bbox=samples[-1].face_bbox,
    )
