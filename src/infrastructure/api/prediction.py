"""Prédictions de l'API : fonctions du notebook (cellules 34 et 46) + stockage."""

import logging
import time
from datetime import UTC, datetime

import pandas as pd

from config.settings import THRESHOLD
from domain.ml_feature import FEATURE_COLUMNS
from infrastructure.api.errors import ApiError
from infrastructure.ml.ml_predict import MLPredict

logger = logging.getLogger(__name__)


def require_model(model_provider):
    loaded_model = model_provider.get()
    if loaded_model is None:
        raise ApiError(503, "model_unavailable", "Aucun modèle n'est chargé")
    return loaded_model


def predict_one(order_id, features, loaded_model):
    start = time.perf_counter()
    result = MLPredict.predict_order_eligibility(
        features, loaded_model.model, threshold=THRESHOLD
    )
    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "order_id": order_id,
        "express_eligible": result["express_eligible"],
        "decision": result["decision"],
        "probability": result["probability"],
        # Version du registre MLflow, pas le MODEL_VERSION fixe du notebook.
        "model_version": loaded_model.version,
        "predicted_at": datetime.now(UTC),
        "latency_ms": round(latency_ms, 3),
    }


def predict_many(order_ids, orders_features, loaded_model):
    start = time.perf_counter()
    input_df = pd.DataFrame(orders_features)[FEATURE_COLUMNS]
    result = MLPredict.batch_predict_orders(
        input_df, loaded_model.model, threshold=THRESHOLD
    )
    latency_ms = (time.perf_counter() - start) * 1000 / len(order_ids)
    predicted_at = datetime.now(UTC)

    return [
        {
            "order_id": order_id,
            "express_eligible": bool(row["express_eligible"]),
            "decision": row["decision"],
            "probability": round(float(row["eligibility_probability"]), 4),
            "model_version": loaded_model.version,
            "predicted_at": predicted_at,
            "latency_ms": round(latency_ms, 3),
        }
        for order_id, row in zip(order_ids, result.to_dict("records"), strict=True)
    ]


def predict_in_background(order_id, features, model_provider, repository):
    """Prédiction asynchrone d'une commande reçue par POST /v1/orders."""
    loaded_model = model_provider.get()
    if loaded_model is None:
        logger.warning("Commande %s non prédite : aucun modèle chargé", order_id)
        return
    try:
        repository.save_predictions([predict_one(order_id, features, loaded_model)])
    except Exception:
        logger.exception("Échec de la prédiction de la commande %s", order_id)
