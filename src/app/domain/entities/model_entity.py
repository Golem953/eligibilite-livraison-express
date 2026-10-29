from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ModelEntity:
    """Fiche du modèle (model card) : métadonnées et métriques (cellule 55 du notebook).

    `FileModelRepository.save()` écrit `metrics.json` et `features.json` à partir de
    ces champs. Les champs de la cellule 55 qui ne servent à rien ici
    (`positive_class`, `training_rows`...) ne sont pas portés : YAGNI.
    """

    project: str
    model_version: str
    model_type: str
    task: str
    target: str
    threshold: float
    features: list[str]
    metrics: dict[str, float]
    trained_at: datetime | None = None
