from collections.abc import Callable
from datetime import UTC, datetime

from domain.entities.order import Order
from domain.interface.order_id_generator_interface import OrderIdGeneratorInterface
from domain.value_objects.customer_type import CustomerType
from domain.value_objects.delivery_zone import DeliveryZone
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.weather import Weather


class OrderFactory:
    """Crée les nouvelles commandes, au statut « reçue ».

    Porte les contrôles de création : une commande invalide n'est jamais créée.
    Une commande relue en base est reconstituée avec Order(...) directement.
    """

    def __init__(
        self,
        id_generator: OrderIdGeneratorInterface,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._id_generator = id_generator
        self._clock = clock

    def create(
        self,
        *,
        hour: int,
        day_of_week: int,
        weekend: bool,
        distance_km: float,
        order_value_eur: float,
        weight_kg: float,
        stock_available: bool,
        preparation_time_min: float,
        carrier_capacity: float,
        weather: str,
        delivery_zone: str,
        customer_type: str,
        order_id: str | None = None,
    ) -> Order:
        """Lève ValueError si une valeur est invalide."""
        if order_id is not None and not order_id:
            raise ValueError("order_id ne doit pas être vide.")
        if not 0 <= hour <= 23:
            raise ValueError("hour doit être compris entre 0 et 23.")
        if not 0 <= day_of_week <= 6:
            raise ValueError("day_of_week doit être compris entre 0 et 6.")
        if distance_km < 0:
            raise ValueError("distance_km doit être positive ou nulle.")
        if order_value_eur < 0:
            raise ValueError("order_value_eur doit être positive ou nulle.")
        if weight_kg < 0:
            raise ValueError("weight_kg doit être positif ou nul.")
        if preparation_time_min < 0:
            raise ValueError("preparation_time_min doit être positif ou nul.")
        if not 0 <= carrier_capacity <= 1:
            raise ValueError("carrier_capacity doit être comprise entre 0 et 1.")

        return Order(
            order_id=order_id or self._id_generator.next_id(),
            order_date=self._clock(),
            hour=hour,
            day_of_week=day_of_week,
            weekend=weekend,
            distance_km=distance_km,
            order_value_eur=order_value_eur,
            weight_kg=weight_kg,
            stock_available=stock_available,
            preparation_time_min=preparation_time_min,
            carrier_capacity=carrier_capacity,
            # Lève ValueError si la valeur ne fait pas partie de l'énumération.
            weather=Weather(weather),
            delivery_zone=DeliveryZone(delivery_zone),
            customer_type=CustomerType(customer_type),
            status=OrderStatus.RECEIVED,
        )
