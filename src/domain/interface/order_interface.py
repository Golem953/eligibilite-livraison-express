from datetime import datetime
from typing import Protocol

from domain.value_objects.customer_type import CustomerType
from domain.value_objects.delivery_zone import DeliveryZone
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.prediction import Prediction
from domain.value_objects.weather import Weather


class OrderInterface(Protocol):
    """Contrat d'une commande : les données que toute commande doit exposer.

    Protocol et non ABC : une classe le respecte dès qu'elle a ces attributs, sans
    en hériter. Une ABC à propriétés abstraites ne fonctionnerait pas avec la
    dataclass Order, dont les champs ne sont pas des attributs de classe.
    Propriétés en lecture seule, car Order est figée (frozen=True).
    """

    @property
    def order_id(self) -> str: ...

    @property
    def order_date(self) -> datetime: ...

    @property
    def hour(self) -> int: ...

    @property
    def day_of_week(self) -> int: ...

    @property
    def weekend(self) -> bool: ...

    @property
    def distance_km(self) -> float: ...

    @property
    def order_value_eur(self) -> float: ...

    @property
    def weight_kg(self) -> float: ...

    @property
    def stock_available(self) -> bool: ...

    @property
    def preparation_time_min(self) -> float: ...

    @property
    def carrier_capacity(self) -> float: ...

    @property
    def weather(self) -> Weather: ...

    @property
    def delivery_zone(self) -> DeliveryZone: ...

    @property
    def customer_type(self) -> CustomerType: ...

    @property
    def status(self) -> OrderStatus: ...

    @property
    def prediction(self) -> Prediction | None: ...

    @property
    def real_label(self) -> bool | None: ...
