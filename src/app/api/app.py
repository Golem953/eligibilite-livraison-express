"""API HTTP minimale de livraison express."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ..core.core import Core
from ..domain.entities import OrderEntity, PredictionEntity

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Créer l'API et charger le modèle persistant si disponible."""
    api = FastAPI(title="Livraison Express Lite")

    try:
        api.state.core = Core(load_model=True)
        api.state.predict_service = api.state.core.get_predict_service()
        if api.state.predict_service is None:
            logger.warning("API démarrée sans modèle chargé")
    except Exception:
        logger.exception("Impossible de charger le modèle au démarrage de l'API")
        api.state.core = None
        api.state.predict_service = None

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


app = create_app()
