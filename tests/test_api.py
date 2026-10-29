"""API HTTP : statuts, contrat de réponse et validation des entrées."""

import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.learning.ml_predict import MLPredict


@pytest.fixture
def client(settings):
    """API démarrée sans modèle : MODEL_PATH pointe vers un fichier qui n'existe pas."""
    return TestClient(create_app(settings))


@pytest.fixture
def client_with_model(fake_model):
    """API avec un modèle factice (probabilité 0,8), fourni sans fichier ni configuration."""
    service = MLPredict(fake_model(0.8), threshold=0.5, model_version="test")
    return TestClient(create_app(predict_service=service))


def test_api_does_not_import_training_code():
    """ADR-0003 : l'API n'importe ni MLflow ni le code d'entraînement.

    Lancé dans un processus séparé, car d'autres tests ont déjà importé MLflow.
    """
    code = (
        "import sys, app.api.app; "
        "loaded = [m for m in ('mlflow', 'app.core.learning.ml_trainer') if m in sys.modules]; "
        "print(','.join(loaded))"
    )
    src = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(src)},
    )

    assert result.stdout.strip() == ""


def test_health_is_always_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_is_503_without_model(client):
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["reason"] == "model_unavailable"


def test_predict_is_503_without_model(client, order):
    response = client.post("/predict", json=asdict(order))

    assert response.status_code == 503


def test_ready_is_200_with_model(client_with_model):
    assert client_with_model.get("/health/ready").status_code == 200


def test_predict_returns_the_prediction_contract(client_with_model, order):
    response = client_with_model.post("/predict", json=asdict(order))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "express_eligible",
        "decision",
        "probability",
        "model_version",
        "prediction_timestamp",
    }
    assert body["express_eligible"] is True
    assert body["decision"] == "oui"
    assert body["probability"] == 0.8


def test_predict_rejects_an_invalid_order(client_with_model, order):
    payload = asdict(order) | {"hour": "pas un nombre"}

    response = client_with_model.post("/predict", json=payload)

    assert response.status_code == 422


def test_predict_rejects_a_missing_field(client_with_model, order):
    payload = asdict(order)
    del payload["distance_km"]

    response = client_with_model.post("/predict", json=payload)

    assert response.status_code == 422
