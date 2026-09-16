"""Settling several frames' answers about the visitor into one."""

import pytest

from tvarometr_inference.attribute_averaging import Sample, average, male_probability

LABELS = ("neutral", "happiness", "sadness")


def sample(age=30.0, male=0.9, emotions=(0.1, 0.8, 0.1), bbox=(0, 0, 100, 120)):
    return Sample(age, male, emotions, bbox)


def test_one_sample_is_its_own_average():
    result = average([sample()], LABELS)
    assert result.age == 30.0
    assert result.gender == "male"
    assert result.emotion == "happiness"
    assert result.emotion_confidence == pytest.approx(0.8)


def test_one_wild_age_does_not_drag_the_median():
    ages = [30.0, 31.0, 32.0, 33.0, 80.0]
    assert average([sample(age=a) for a in ages], LABELS).age == 32.0


def test_male_probability_turns_mivolos_answer_around_for_female():
    assert male_probability("male", 0.9) == pytest.approx(0.9)
    assert male_probability("female", 0.9) == pytest.approx(0.1)


def test_a_confident_frame_outweighs_two_hesitant_ones_on_gender():
    # Two frames lean male a little, one is sure the visitor is female.
    samples = [sample(male=0.55), sample(male=0.55), sample(male=0.1)]
    assert average(samples, LABELS).gender == "female"


def test_emotion_is_the_best_of_the_averaged_probabilities():
    # Happiness wins two frames narrowly, neutral wins one by a mile.
    samples = [
        sample(emotions=(0.4, 0.6, 0.0)),
        sample(emotions=(0.4, 0.6, 0.0)),
        sample(emotions=(0.9, 0.1, 0.0)),
    ]
    result = average(samples, LABELS)
    assert result.emotion == "neutral"
    assert result.emotion_confidence == pytest.approx(1.7 / 3)


def test_the_face_box_is_the_one_from_the_last_frame():
    samples = [sample(bbox=(0, 0, 10, 10)), sample(bbox=(5, 5, 50, 60))]
    assert average(samples, LABELS).face_bbox == (5, 5, 50, 60)
