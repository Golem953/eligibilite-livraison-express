"""Prédiction : la probabilité du modèle devient une décision selon le seuil."""

import pytest

from app.core.learning.ml_predict import MLPredict


@pytest.fixture
def predictor(fake_model):
    """predictor(0.8) : un MLPredict dont le modèle prédit toujours 0,8."""

    def build(probability: float, threshold: float = 0.5) -> MLPredict:
        return MLPredict(fake_model(probability), threshold=threshold, model_version="test")

    return build


@pytest.mark.parametrize(
    ("probability", "eligible", "decision"),
    [(0.8, True, "oui"), (0.5, True, "oui"), (0.2, False, "non")],
)
def test_decision_follows_threshold(order, predictor, probability, eligible, decision):
    prediction = predictor(probability).predict(order)

    assert prediction.express_eligible is eligible
    assert prediction.decision == decision


def test_threshold_is_configurable(order, predictor):
    prediction = predictor(0.6, threshold=0.7).predict(order)

    assert prediction.decision == "non"


def test_probability_is_rounded(order, predictor):
    prediction = predictor(0.123456).predict(order)

    assert prediction.probability == 0.1235


def test_prediction_carries_version_and_timestamp(order, predictor):
    prediction = predictor(0.9).predict(order)

    assert prediction.model_version == "test"
    assert prediction.prediction_timestamp.endswith("+00:00")
