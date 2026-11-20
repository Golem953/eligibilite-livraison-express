"""Canary du modèle (ADR-0005) : une part des commandes est prédite par le nouveau modèle."""

from __future__ import annotations

import logging
import time
import uuid
import zlib
from dataclasses import replace

from ...domain.entities.order_entity import OrderEntity
from ...domain.entities.prediction_entity import PredictionEntity
from .ml_predict import MLPredict

logger = logging.getLogger(__name__)


class CanaryPredict:
    """Envoie `percent` % des commandes au modèle canary, les autres au modèle stable.

    L'affectation dépend de `order_id`, avec crc32 (contrairement à `hash()`, il ne change
    pas d'un démarrage à l'autre) : une même commande est toujours prédite par le même
    modèle. Une commande sans identifiant en reçoit un, renvoyé dans la prédiction.
    """

    def __init__(self, stable: MLPredict, canary: MLPredict, percent: int):
        self.stable = stable
        self.canary = canary
        self.percent = percent

    def uses_canary(self, order_id: str) -> bool:
        return zlib.crc32(order_id.encode()) % 100 < self.percent

    def predict(self, order: OrderEntity) -> PredictionEntity:
        if not order.order_id:
            order = replace(order, order_id=str(uuid.uuid4()))
        is_canary = self.uses_canary(order.order_id)
        service = self.canary if is_canary else self.stable

        # Une ligne par prédiction : c'est elle qui permet de comparer les deux modèles,
        # puisque l'API n'enregistre pas ses prédictions (ADR-0001).
        start = time.perf_counter()
        try:
            prediction = service.predict(order)
        except Exception:
            logger.exception(
                "Prédiction en échec (order_id=%s, canary=%s, model_version=%s)",
                order.order_id,
                is_canary,
                service.model_version,
            )
            raise
        logger.info(
            "Prédiction (order_id=%s, canary=%s, model_version=%s, latency_ms=%.1f, decision=%s)",
            order.order_id,
            is_canary,
            service.model_version,
            (time.perf_counter() - start) * 1000,
            prediction.decision,
        )
        return prediction
