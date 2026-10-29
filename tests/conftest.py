"""Fixtures partagées par les tests."""

from __future__ import annotations

import pytest
from fakes.fake_model import FakeModel
from fakes.fake_tracker import FakeTracker

from app.config import Settings
from app.domain.entities.order_entity import OrderEntity


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
