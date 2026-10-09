from datetime import datetime
from typing import Any

from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from domain.entities.order import Order
from domain.value_objects.customer_type import CustomerType
from domain.value_objects.delivery_zone import DeliveryZone
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.prediction import Prediction
from domain.value_objects.weather import Weather
from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
    DatabaseConstraintError,
    Row,
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
            self._connector.execute(
                """
                INSERT INTO orders (
                    order_id, order_date, hour, day_of_week, weekend,
                    distance_km, order_value_eur, weight_kg, stock_available,
                    preparation_time_min, carrier_capacity,
                    weather, delivery_zone, customer_type,
                    status, predicted_eligible, eligibility_probability,
                    model_version, predicted_at, real_label
                ) VALUES (
                    :order_id, :order_date, :hour, :day_of_week, :weekend,
                    :distance_km, :order_value_eur, :weight_kg, :stock_available,
                    :preparation_time_min, :carrier_capacity,
                    :weather, :delivery_zone, :customer_type,
                    :status, :predicted_eligible, :eligibility_probability,
                    :model_version, :predicted_at, :real_label
                )
                """,
                _order_to_params(order),
            )
        except DatabaseConstraintError as error:
            # Identifiant déjà utilisé (clé primaire) ou valeur refusée par un CHECK.
            raise ValueError(f"Commande {order.order_id} refusée : {error}") from error

    def get_order_by_id(self, order_id: str) -> Order | None:
        """Renvoie la commande, ou None si aucune commande n'a cet identifiant."""
        row = self._connector.fetch_one(
            """
                SELECT
                    order_id, order_date, hour, day_of_week, weekend,
                    distance_km, order_value_eur, weight_kg, stock_available,
                    preparation_time_min, carrier_capacity,
                    weather, delivery_zone, customer_type,
                    status, predicted_eligible, eligibility_probability,
                    model_version, predicted_at, real_label
                FROM orders
                WHERE order_id = :order_id
            """,
            {"order_id": order_id},
        )
        return _row_to_order(row) if row is not None else None

    def find_labelled(self) -> list[Order]:
        rows = self._connector.fetch_all(
            """
                SELECT
                    order_id, order_date, hour, day_of_week, weekend,
                    distance_km, order_value_eur, weight_kg, stock_available,
                    preparation_time_min, carrier_capacity,
                    weather, delivery_zone, customer_type,
                    status, predicted_eligible, eligibility_probability,
                    model_version, predicted_at, real_label
                FROM orders
                WHERE real_label IS NOT NULL
                ORDER BY order_date
            """
        )
        return [_row_to_order(row) for row in rows]


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


def _row_to_order(row: Row) -> Order:
    """Reconstitue une commande déjà enregistrée.

    Order(...) directement, pas OrderFactory : la fabrique crée les nouvelles
    commandes (id, date, statut « reçue »), alors qu'ici tout vient de la base.
    Les conversions absorbent les écarts entre moteurs : SQLite renvoie 0/1 pour
    les booléens et du texte pour les dates, PostgreSQL des bool et des datetime.
    """
    prediction = None
    if row["predicted_eligible"] is not None:
        prediction = Prediction(
            eligible=bool(row["predicted_eligible"]),
            probability=float(row["eligibility_probability"]),
            model_version=row["model_version"],
            predicted_at=_to_datetime(row["predicted_at"]),
        )
    return Order(
        order_id=row["order_id"],
        order_date=_to_datetime(row["order_date"]),
        hour=int(row["hour"]),
        day_of_week=int(row["day_of_week"]),
        weekend=bool(row["weekend"]),
        distance_km=float(row["distance_km"]),
        order_value_eur=float(row["order_value_eur"]),
        weight_kg=float(row["weight_kg"]),
        stock_available=bool(row["stock_available"]),
        preparation_time_min=float(row["preparation_time_min"]),
        carrier_capacity=float(row["carrier_capacity"]),
        weather=Weather(row["weather"]),
        delivery_zone=DeliveryZone(row["delivery_zone"]),
        customer_type=CustomerType(row["customer_type"]),
        status=OrderStatus(row["status"]),
        prediction=prediction,
        real_label=None if row["real_label"] is None else bool(row["real_label"]),
    )


def _to_datetime(value: datetime | str) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)
