from typing import Any

from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from domain.entities.order import Order
from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
    DatabaseConstraintError,
)

_COLUMNS = (
    "order_id",
    "order_date",
    "hour",
    "day_of_week",
    "weekend",
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
    "weather",
    "delivery_zone",
    "customer_type",
    "status",
    "predicted_eligible",
    "eligibility_probability",
    "model_version",
    "predicted_at",
    "real_label",
)
_INSERT = (
    f"INSERT INTO orders ({', '.join(_COLUMNS)})"
    f" VALUES ({', '.join(f':{column}' for column in _COLUMNS)})"
)


class SqlOrderRepository(OrderRepositoryInterface):
    """Adapter SQL du port OrderRepositoryInterface, commun à tous les moteurs.

    Le SQL écrit ici est standard : seul le connecteur injecté dépend
    du moteur (ADR-0001).
    """

    def __init__(self, connector: DatabaseConnectorInterface) -> None:
        self._connector = connector

    def save(self, order: Order) -> None:
        try:
            self._connector.execute(_INSERT, _order_to_params(order))
        except DatabaseConstraintError as error:
            # Identifiant déjà utilisé (clé primaire) ou valeur refusée par un CHECK.
            raise ValueError(f"Commande {order.order_id} refusée : {error}") from error


def _order_to_params(order: Order) -> dict[str, Any]:
    prediction = order.prediction
    return {
        "order_id": order.order_id,
        "order_date": order.order_date,
        "hour": order.hour,
        "day_of_week": order.day_of_week,
        "weekend": order.weekend,
        "distance_km": order.distance_km,
        "order_value_eur": order.order_value_eur,
        "weight_kg": order.weight_kg,
        "stock_available": order.stock_available,
        "preparation_time_min": order.preparation_time_min,
        "carrier_capacity": order.carrier_capacity,
        # str() : la valeur texte de l'enum ("pluie"), comprise par tous les pilotes.
        "weather": str(order.weather),
        "delivery_zone": str(order.delivery_zone),
        "customer_type": str(order.customer_type),
        "status": str(order.status),
        "predicted_eligible": prediction.eligible if prediction else None,
        "eligibility_probability": prediction.probability if prediction else None,
        "model_version": prediction.model_version if prediction else None,
        "predicted_at": prediction.predicted_at if prediction else None,
        "real_label": order.real_label,
    }
