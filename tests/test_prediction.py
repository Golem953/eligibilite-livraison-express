"""Tests fonctionnels de la prédiction (cellule 39 du notebook)."""

import pytest

from infrastructure.ml.ml_predict import MLPredict
from tests.conftest import VALID_ORDER


def test_valid_order_gives_a_decision(trained_model):
    result = MLPredict.predict_order_eligibility(VALID_ORDER, trained_model)

    assert result["decision"] in {"oui", "non"}
    assert isinstance(result["express_eligible"], bool)
    assert 0 <= result["probability"] <= 1
    assert "model_version" in result


def test_missing_feature_is_rejected(trained_model):
    invalid_order = VALID_ORDER.copy()
    del invalid_order["distance_km"]

    with pytest.raises(ValueError):
        MLPredict.predict_order_eligibility(invalid_order, trained_model)
