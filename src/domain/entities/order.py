from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.customer_type import CustomerType
from domain.value_objects.delivery_zone import DeliveryZone
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.prediction import Prediction
from domain.value_objects.weather import Weather


@dataclass(frozen=True)
class Order:
    """Commande reçue par l'API. Une commande invalide ne peut pas être construite."""

    order_id: str
    order_date: datetime
    hour: int
    day_of_week: int
    weekend: bool
    distance_km: float
    order_value_eur: float
    weight_kg: float
    stock_available: bool
    preparation_time_min: float
    carrier_capacity: float
    weather: Weather
    delivery_zone: DeliveryZone
    customer_type: CustomerType
    status: OrderStatus = OrderStatus.RECEIVED
    prediction: Prediction | None = None
    real_label: bool | None = None

    def __post_init__(self) -> None:
        if not self.order_id:
            raise ValueError("order_id ne doit pas être vide.")
        if not 0 <= self.hour <= 23:
            raise ValueError("hour doit être compris entre 0 et 23.")
        if not 0 <= self.day_of_week <= 6:
            raise ValueError("day_of_week doit être compris entre 0 et 6.")
        if self.distance_km < 0:
            raise ValueError("distance_km doit être positive ou nulle.")
        if self.order_value_eur < 0:
            raise ValueError("order_value_eur doit être positive ou nulle.")
        if self.weight_kg < 0:
            raise ValueError("weight_kg doit être positif ou nul.")
        if self.preparation_time_min < 0:
            raise ValueError("preparation_time_min doit être positif ou nul.")
        if not 0 <= self.carrier_capacity <= 1:
            raise ValueError("carrier_capacity doit être comprise entre 0 et 1.")
        # Le constructeur ne convertit pas : on vérifie que les valeurs
        # catégorielles sont bien des membres des énumérations.
        Weather(self.weather)
        DeliveryZone(self.delivery_zone)
        CustomerType(self.customer_type)
