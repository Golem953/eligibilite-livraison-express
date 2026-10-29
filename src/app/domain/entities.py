from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderEntity:
    hour: int
    day_of_week: int
    weekend: int
    distance_km: float
    order_value_eur: float
    weight_kg: float
    stock_available: int
    preparation_time_min: float
    carrier_capacity: float
    weather: str
    delivery_zone: str
    customer_type: str
    order_id: str | None = None


@dataclass(frozen=True)
class PredictionEntity:
    """Résultat métier d'une prédiction d'éligibilité."""

    express_eligible: bool
    decision: str
    probability: float
    model_version: str
    prediction_timestamp: str


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
