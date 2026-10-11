"""Schémas de l'API, alignés sur doc/openapi.yml."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Weather = Literal["normal", "pluie", "neige", "orage"]
DeliveryZone = Literal["centre", "proche_banlieue", "banlieue", "rurale"]
CustomerType = Literal["standard", "premium"]


class OrderFeatures(BaseModel):
    """Variables d'une commande : FEATURE_COLUMNS (cellule 20 du notebook).

    Une variable absente ou en trop produit une erreur 422.
    """

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Identifiant métier de la commande. Généré par le serveur si absent."
        ),
        examples=["CMD-000001"],
    )
    hour: int = Field(ge=0, le=23, examples=[14])
    day_of_week: int = Field(
        ge=0, le=6, description="0 = lundi ... 6 = dimanche", examples=[2]
    )
    weekend: Literal[0, 1] = Field(examples=[0])
    distance_km: float = Field(ge=0, examples=[3.5])
    order_value_eur: float = Field(ge=0, examples=[89.9])
    weight_kg: float = Field(ge=0, examples=[2.4])
    stock_available: Literal[0, 1] = Field(examples=[1])
    preparation_time_min: float = Field(ge=0, examples=[18])
    carrier_capacity: float = Field(ge=0, le=1, examples=[0.85])
    weather: Weather = Field(examples=["normal"])
    delivery_zone: DeliveryZone = Field(examples=["centre"])
    customer_type: CustomerType = Field(examples=["premium"])


class OrderAccepted(BaseModel):
    order_id: str = Field(examples=["CMD-000001"])
    status: Literal["accepted"] = "accepted"


class Prediction(BaseModel):
    """Résultat d'une prédiction, aligné sur la cellule 34 du notebook."""

    order_id: str = Field(examples=["CMD-000001"])
    express_eligible: bool = Field(examples=[True])
    decision: Literal["oui", "non"] = Field(examples=["oui"])
    probability: float = Field(ge=0, le=1, examples=[0.8734])
    model_version: str = Field(examples=["1"])
    predicted_at: datetime
    latency_ms: float | None = Field(
        default=None,
        description="Temps de calcul de la prédiction, pour l'observabilité (séance 7)",
    )


class BatchPredictionRequest(BaseModel):
    orders: list[OrderFeatures] = Field(min_length=1, max_length=1000)


class BatchPredictionResponse(BaseModel):
    predictions: list[Prediction]
    count: int = Field(examples=[3])


class ModelCardResponse(BaseModel):
    """Model card de la cellule 55 du notebook."""

    project: str = Field(examples=["eligibilite-livraison-express"])
    model_version: str = Field(examples=["1"])
    model_type: str = Field(examples=["Régression logistique"])
    task: str = Field(examples=["Classification binaire"])
    target: str = Field(examples=["express_eligible"])
    threshold: float = Field(examples=[0.5])
    trained_at: datetime | None = None
    features: list[str]
    metrics: dict[str, float]
    limitations: list[str] = []


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = Field(examples=["eligibilite-livraison-express"])
    version: str = Field(examples=["1.0.0"])


class ReadinessStatus(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str] = Field(
        examples=[{"model": "loaded", "order_store": "reachable"}]
    )
    version: str | None = None


class Error(BaseModel):
    error: str = Field(
        description="Code d'erreur stable, branchable côté client",
        examples=["validation_error"],
    )
    message: str = Field(
        description="Message destiné à l'humain, non contractuel",
        examples=["Feature manquante : distance_km"],
    )
    details: list[str] | None = None
