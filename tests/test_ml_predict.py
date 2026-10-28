"""Prédiction : la probabilité du modèle devient une décision selon le seuil."""

import pytest

from app.core.learning.ml_predict import MLPredict


@pytest.mark.parametrize(
    ("probability", "eligible", "decision"),
    [(0.8, True, "oui"), (0.5, True, "oui"), (0.2, False, "non")],
)
def test_decision_follows_threshold(order, fake_model, probability, eligible, decision):
    prediction = MLPredict(fake_model(probability), threshold=0.5).predict(order)

    assert prediction.express_eligible is eligible
    assert prediction.decision == decision


def test_threshold_is_configurable(order, fake_model):
    prediction = MLPredict(fake_model(0.6), threshold=0.7).predict(order)

    assert prediction.decision == "non"


def test_probability_is_rounded(order, fake_model):
    prediction = MLPredict(fake_model(0.123456), threshold=0.5).predict(order)

    assert prediction.probability == 0.1235


def test_prediction_carries_version_and_timestamp(order, fake_model):
    prediction = MLPredict(fake_model(0.9), threshold=0.5).predict(order)

    assert prediction.model_version
    assert prediction.prediction_timestamp.endswith("+00:00")
