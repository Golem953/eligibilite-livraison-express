"""Schémas du contrat OpenAPI partagés par les controllers."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.entities.order import Order


class ErrorResponse(BaseModel):
    """Schéma Error du contrat OpenAPI."""

    error: str
    message: str
    details: list[str] | None = None


class OrderFeatures(BaseModel):
    """Schéma OrderFeatures du contrat : toute variable en trop donne une 422."""

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = Field(default=None, min_length=1, max_length=50)
    hour: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    weekend: Literal[0, 1]
    distance_km: float = Field(ge=0)
    order_value_eur: float = Field(ge=0)
    weight_kg: float = Field(ge=0)
    stock_available: Literal[0, 1]
    preparation_time_min: float = Field(ge=0)
    carrier_capacity: float = Field(ge=0, le=1)
    weather: Literal["normal", "pluie", "neige", "orage"]
    delivery_zone: Literal["centre", "proche_banlieue", "banlieue", "rurale"]
    customer_type: Literal["standard", "premium"]

    def to_features(self) -> dict[str, Any]:
        """HTTP → domaine : variables de la commande, 0/1 du contrat en booléens."""
        features = self.model_dump(exclude={"order_id"})
        features["weekend"] = bool(features["weekend"])
        features["stock_available"] = bool(features["stock_available"])
        return features

    @classmethod
    def from_order(cls, order: Order) -> "OrderFeatures":
        """Domaine → HTTP : les booléens repassent en 0/1 comme dans le contrat."""
        return cls(
            order_id=order.order_id,
            hour=order.hour,
            day_of_week=order.day_of_week,
            weekend=int(order.weekend),
            distance_km=order.distance_km,
            order_value_eur=order.order_value_eur,
            weight_kg=order.weight_kg,
            stock_available=int(order.stock_available),
            preparation_time_min=order.preparation_time_min,
            carrier_capacity=order.carrier_capacity,
            weather=order.weather,
            delivery_zone=order.delivery_zone,
            customer_type=order.customer_type,
        )
