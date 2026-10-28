"""API HTTP : statuts, contrat de réponse et validation des entrées."""

from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.learning.ml_predict import MLPredict


@pytest.fixture
def api(isolated_env):
    """API démarrée sans modèle : MODEL_PATH pointe vers un fichier qui n'existe pas."""
    return create_app()


@pytest.fixture
def client(api):
    return TestClient(api)


@pytest.fixture
def client_with_model(api, fake_model):
    """API dont le modèle est remplacé par un modèle factice (probabilité 0,8)."""
    api.state.predict_service = MLPredict(fake_model(0.8), threshold=0.5)
    return TestClient(api)


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
