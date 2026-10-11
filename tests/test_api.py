"""Routes de l'API, comparées au contrat doc/openapi.yml (séances 1, 3 et 5)."""

from tests.conftest import VALID_ORDER


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_with_model(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"model": "loaded", "order_store": "reachable"}


def test_not_ready_without_model(client_without_model):
    response = client_without_model.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_create_order_then_read_order_and_its_prediction(client):
    response = client.post("/v1/orders", json=VALID_ORDER)

    assert response.status_code == 202
    order_id = response.json()["order_id"]
    assert order_id == "CMD-000001"
    assert response.json()["status"] == "accepted"

    assert client.get(f"/v1/orders/{order_id}").json() == {
        "order_id": order_id,
        **VALID_ORDER,
    }
    # La tâche de fond a prédit la commande après la réponse.
    prediction = client.get(f"/v1/predictions/{order_id}").json()
    assert prediction["decision"] in {"oui", "non"}
    assert prediction["model_version"] == "3"


def test_order_with_client_id_and_duplicate(client):
    order = {**VALID_ORDER, "order_id": "EXT-42"}

    assert client.post("/v1/orders", json=order).json()["order_id"] == "EXT-42"
    response = client.post("/v1/orders", json=order)

    assert response.status_code == 422
    assert response.json()["error"] == "order_rejected"


def test_missing_or_extra_feature_gives_422(client):
    missing = {k: v for k, v in VALID_ORDER.items() if k != "distance_km"}
    extra = {**VALID_ORDER, "colour": "red"}

    for body in (missing, extra):
        response = client.post("/v1/predictions", json=body)
        assert response.status_code == 422
        assert response.json()["error"] == "validation_error"


def test_out_of_range_value_gives_422(client):
    response = client.post("/v1/orders", json={**VALID_ORDER, "hour": 24})

    assert response.status_code == 422


def test_unknown_order_gives_404(client):
    response = client.get("/v1/orders/CMD-999999")

    assert response.status_code == 404
    assert response.json()["error"] == "order_not_found"


def test_create_prediction(client):
    response = client.post("/v1/predictions", json=VALID_ORDER)

    assert response.status_code == 200
    prediction = response.json()
    assert prediction["decision"] in {"oui", "non"}
    assert prediction["express_eligible"] == (prediction["decision"] == "oui")
    assert 0 <= prediction["probability"] <= 1
    assert prediction["latency_ms"] >= 0
    assert client.get(f"/v1/predictions/{prediction['order_id']}").status_code == 200


def test_prediction_without_model_gives_503(client_without_model):
    response = client_without_model.post("/v1/predictions", json=VALID_ORDER)

    assert response.status_code == 503
    assert response.json()["error"] == "model_unavailable"


def test_batch_predictions_keep_order(client):
    far_order = {**VALID_ORDER, "distance_km": 60, "stock_available": 0}
    response = client.post(
        "/v1/predictions/batch", json={"orders": [VALID_ORDER, far_order]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    first, second = body["predictions"]
    assert first["probability"] > second["probability"]


def test_empty_batch_gives_422(client):
    assert client.post("/v1/predictions/batch", json={"orders": []}).status_code == 422


def test_model_card(client):
    response = client.get("/v1/model")

    assert response.status_code == 200
    card = response.json()
    assert card["model_version"] == "3"
    assert card["target"] == "express_eligible"
    assert card["metrics"]["f1_score"] == 0.86
