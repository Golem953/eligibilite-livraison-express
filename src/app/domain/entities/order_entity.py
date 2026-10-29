from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderEntity:
    """Commande à évaluer : les variables du modèle et un identifiant facultatif."""

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
