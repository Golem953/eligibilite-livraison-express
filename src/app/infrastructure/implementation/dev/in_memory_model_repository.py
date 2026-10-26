"""`ModelRepository` de développement : le `.joblib` du notebook, chargé une fois.

Implémentation de l'abstraction `ModelRepository`.

Le notebook (cellule 41) écrit `express_delivery_model.joblib` dans `artifacts/`.
Cet adaptateur charge ce fichier et le garde en mémoire. C'est exactement ce que fait
un service de production au démarrage, et la cellule 43 du notebook (`joblib.load`)
en montre le code.

Ce fichier illustre deux décisions importantes :

- le modèle est chargé **une fois** au démarrage, pas à chaque requête
- l'absence de modèle n'est pas fatale : elle est signalée, et l'API répond 503 sur les
  prédictions tant qu'il n'y a rien à prédire.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib

from ...model_repository import ModelRepository
from ....domain.entities import ModelEntity

logger = logging.getLogger(__name__)


class FileModelRepository(ModelRepository):
    """Enregistre les artifacts du modèle dans le système de fichiers local."""

    def __init__(self, model_path: str):
        self._model_path = Path(model_path)
        self._model: object | None = None
        self._model_card: ModelEntity | None = None

    def save(self, model: object, model_card: ModelEntity) -> None:
        """Enregistre les artifacts du modèle dans le système de fichiers local."""
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self._model_path)
        (self._model_path.parent / "metrics.json").write_text(
            json.dumps(model_card.metrics, indent=2, sort_keys=True)
        )
        (self._model_path.parent / "features.json").write_text(
            json.dumps(model_card.features, indent=2)
        )
        self._model = model
        self._model_card = model_card

    def load(self, version: str = "") -> object | None:
        """Charge le modèle."""
        if not self._model_path.exists():
            return None
        model = joblib.load(self._model_path)
        self._model = model
        logger.info("Modèle chargé depuis %s", self._model_path)
        return model
