"""Canary du modèle (ADR-0005) : répartition des commandes entre le modèle stable et le canary."""

from dataclasses import replace
from pathlib import Path

import joblib
import pytest

from app.core.core import build_prediction_service
from app.core.learning.canary_predict import CanaryPredict
from app.core.learning.ml_predict import MLPredict


@pytest.fixture
def canary(fake_model):
    """canary(10) : 10 % des commandes sur le modèle « canary », le reste sur « stable »."""

    def build(percent: int) -> CanaryPredict:
        stable = MLPredict(fake_model(0.2), threshold=0.5, model_version="stable")
        new = MLPredict(fake_model(0.8), threshold=0.5, model_version="canary")
        return CanaryPredict(stable, new, percent)

    return build


def versions(service, order, count=1000):
    return [
        service.predict(replace(order, order_id=f"CMD-{i}")).model_version for i in range(count)
    ]


@pytest.mark.parametrize(("percent", "expected"), [(0, {"stable"}), (100, {"canary"})])
def test_all_or_nothing(canary, order, percent, expected):
    assert set(versions(canary(percent), order)) == expected


def test_ten_percent_goes_to_canary(canary, order):
    share = versions(canary(10), order).count("canary") / 1000

    assert 0.07 < share < 0.13


def test_same_order_always_gets_the_same_model(canary, order):
    assert versions(canary(10), order) == versions(canary(10), order)


def test_missing_order_id_is_generated_and_returned(canary, order):
    prediction = canary(10).predict(replace(order, order_id=None))

    assert prediction.order_id


def save(model, path) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return str(path)


def test_build_without_canary_file_serves_stable_only(settings, fake_model, tmp_path):
    save(fake_model(0.2), settings.model_path)
    settings = settings.model_copy(
        update={"canary_percent": 10, "canary_model_path": str(tmp_path / "absent.joblib")}
    )

    assert isinstance(build_prediction_service(settings), MLPredict)


def test_build_with_canary_file_splits_traffic(settings, fake_model, tmp_path):
    save(fake_model(0.2), settings.model_path)
    canary_path = save(fake_model(0.8), tmp_path / "canary" / "model.joblib")
    settings = settings.model_copy(
        update={
            "canary_percent": 10,
            "canary_model_path": canary_path,
            "canary_model_version": "2.0.0",
        }
    )

    service = build_prediction_service(settings)

    assert isinstance(service, CanaryPredict)
    assert service.canary.model_version == "2.0.0"
