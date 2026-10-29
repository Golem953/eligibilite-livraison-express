"""Cas d'usage « entraîner le modèle » : lire les données, entraîner, enregistrer."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..domain.entities.model_entity import ModelEntity
from ..domain.interface.model_repository_interface import ModelRepositoryInterface
from ..domain.interface.order_repository_interface import OrderRepositoryInterface
from .learning.ml_trainer import MLTrainer
from .learning.order_feature import FEATURE_COLUMNS, TARGET_COLUMN
from .training_result import TrainingResult

logger = logging.getLogger(__name__)


class TrainingService:
    """Orchestre un entraînement. Ne connaît que des interfaces, aucune technologie."""

    def __init__(
        self,
        order_repository: OrderRepositoryInterface,
        trainer: MLTrainer,
        model_repository: ModelRepositoryInterface,
        model_version: str,
        threshold: float,
    ):
        self._order_repository = order_repository
        self._trainer = trainer
        self._model_repository = model_repository
        self._model_version = model_version
        self._threshold = threshold

    def run(self) -> TrainingResult:
        orders, labels = self._order_repository.get_training_data()
        logger.info("Données prêtes (commandes=%d)", len(orders))
        run_id, metrics = self._trainer.train(orders, labels)

        model_card = ModelEntity(
            project="livraison-express-lite",
            model_version=self._model_version,
            model_type=self._trainer.model_type,
            task="classification binaire",
            target=TARGET_COLUMN,
            threshold=self._threshold,
            features=list(FEATURE_COLUMNS),
            metrics=metrics,
            trained_at=datetime.now(timezone.utc),
        )
        self._model_repository.save(self._trainer.model_pipeline, model_card)
        logger.info("Modèle enregistré (version=%s, run_id=%s)", self._model_version, run_id)
        return TrainingResult(run_id=run_id, metrics=metrics)
