"""Fixtures partagées par les tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.config import Settings
from app.domain.entities import OrderEntity
from app.domain.ports import ExperimentTracker


class FakeModel:
    """Modèle factice : renvoie toujours la même probabilité, sans entraînement."""

    def __init__(self, probability: float):
        self.probability = probability

    def predict_proba(self, features):
        return np.array([[1 - self.probability, self.probability]] * len(features))


class FakeTracker(ExperimentTracker):
    """Tracker factice : garde en mémoire ce qu'on lui envoie, sans MLflow."""

    def __init__(self):
        self.runs: list[dict] = []

    def log_run(self, run_name, params, metrics, model) -> str:
        self.runs.append({"run_name": run_name, "params": params, "metrics": metrics})
        return f"run-{len(self.runs)}"


@pytest.fixture
def fake_model():
    """Fabrique de modèles factices : fake_model(0.8) prédit toujours 0,8."""
    return FakeModel


@pytest.fixture
def fake_tracker() -> FakeTracker:
    return FakeTracker()


@pytest.fixture
def order() -> OrderEntity:
    """La commande d'exemple du dépôt (order.json)."""
    return OrderEntity(
        hour=14,
        day_of_week=2,
        weekend=0,
        distance_km=3.5,
        order_value_eur=89.9,
        weight_kg=2.4,
        stock_available=1,
        preparation_time_min=18,
        carrier_capacity=0.85,
        weather="normal",
        delivery_zone="centre",
        customer_type="premium",
        order_id="CMD-TEST",
    )


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    """Configuration isolée : modèle et runs MLflow dans un dossier temporaire."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
    return Settings(model_path=str(tmp_path / "artifacts" / "model.joblib"))
