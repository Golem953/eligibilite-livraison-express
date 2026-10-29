"""`ModelRepository` de développement : le modèle dans un fichier `.joblib` local.

Le notebook (cellule 41) écrit `express_delivery_model.joblib` dans `artifacts/`, et la
cellule 43 le relit avec `joblib.load`. Cette implémentation fait la même chose.

L'absence de modèle n'est pas fatale : `load` renvoie `None`, et l'API répond 503 sur
les prédictions tant qu'il n'y a rien à prédire.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib

from ....domain.entities import ModelEntity
from ....domain.ports import ModelRepository

logger = logging.getLogger(__name__)


class FileModelRepository(ModelRepository):
    """Enregistre le modèle et sa fiche dans le système de fichiers local."""

    def __init__(self, model_path: str):
        self._model_path = Path(model_path)

    def save(self, model: object, model_card: ModelEntity) -> None:
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self._model_path)
        (self._model_path.parent / "metrics.json").write_text(
            json.dumps(model_card.metrics, indent=2, sort_keys=True)
        )
        (self._model_path.parent / "features.json").write_text(
            json.dumps(model_card.features, indent=2)
        )

    def load(self) -> object | None:
        if not self._model_path.exists():
            return None
        model = joblib.load(self._model_path)
        logger.info("Modèle chargé depuis %s", self._model_path)
        return model
