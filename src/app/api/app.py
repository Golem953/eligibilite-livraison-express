"""API HTTP minimale de livraison express."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ..config import Settings
from ..core.core import build_prediction_service
from ..core.learning.ml_predict import MLPredict
from ..domain.entities import OrderEntity, PredictionEntity

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    predict_service: MLPredict | None = None,
) -> FastAPI:
    """Créer l'API.

    Sans `predict_service`, le modèle enregistré est chargé une seule fois, ici. Les
    tests peuvent en fournir un directement, sans fichier ni configuration.
    """
    api = FastAPI(title="Livraison Express Lite")

    if predict_service is None:
        try:
            predict_service = build_prediction_service(settings or Settings())
        except Exception:
            logger.exception("Impossible de charger le modèle au démarrage de l'API")
    if predict_service is None:
        logger.warning("API démarrée sans modèle chargé")
    api.state.predict_service = predict_service

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/health/ready")
    def health_ready(request: Request):
        if request.app.state.predict_service is None:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "model_unavailable"},
            )
        return {"status": "ready"}

    @api.post("/predict", response_model=PredictionEntity)
    def predict(payload: OrderEntity, request: Request) -> PredictionEntity:
        predict_service = request.app.state.predict_service
        if predict_service is None:
            raise HTTPException(status_code=503, detail="Modèle indisponible")

        return predict_service.predict(payload)

    return api
