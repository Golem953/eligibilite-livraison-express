from __future__ import annotations

from dataclasses import dataclass, field
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
    """Métadonnées et métriques du modèle en service (cellule 55 du notebook).

    Déclaré dès la séance 1, et non en séance 3 comme le prévoyait le squelette :
    `FileModelRepository.save()` écrit `metrics.json` et `features.json` à partir de
    ces champs, donc `python -m livraison_express train` (définition de terminé de la
    séance 1) ne peut pas exister sans eux. La séance 3 ajoutera l'endpoint
    `GET /v1/model` qui les expose.

    Champs alignés champ pour champ sur le schéma `ModelEntity` de
    `docs/api/openapi.yml`. Les champs de la cellule 55 absents du contrat
    (`positive_class`, `training_rows`...) ne sont pas portés : le contrat fait foi,
    et YAGNI s'applique aux champs de réponse comme au code.
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
    limitations: list[str] = field(default_factory=list)
