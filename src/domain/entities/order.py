from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.customer_type import CustomerType
from domain.value_objects.delivery_zone import DeliveryZone
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.prediction import Prediction
from domain.value_objects.weather import Weather


@dataclass(frozen=True)
class Order:
    """Commande reçue par l'API.

    Une nouvelle commande se crée avec OrderFactory, qui porte les contrôles.
    """

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
