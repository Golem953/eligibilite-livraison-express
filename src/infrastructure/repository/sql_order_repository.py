from datetime import datetime
from typing import Any

from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from domain.entities.order import Order, OrderStatus, Prediction
from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
    DatabaseConstraintError,
    Row,
)

_FEATURE_COLUMNS = (
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
)
_STATE_COLUMNS = (
    "status",
    "predicted_eligible",
    "eligibility_probability",
    "model_version",
    "predicted_at",
    "real_label",
)
_ALL_COLUMNS = _FEATURE_COLUMNS + _STATE_COLUMNS
_SELECT = f"SELECT {', '.join(_ALL_COLUMNS)} FROM orders"


class SqlOrderRepository(OrderRepositoryInterface):
    """Adapter SQL du port OrderRepositoryInterface, commun à tous les moteurs.

    Le SQL écrit ici est standard : seul le connecteur injecté dépend
    du moteur (ADR-0001).
    """

    def __init__(self, connector: DatabaseConnectorInterface) -> None:
        self._connector = connector

    def save(self, order: Order) -> None:
        columns = ", ".join(_ALL_COLUMNS)
        placeholders = ", ".join(f":{column}" for column in _ALL_COLUMNS)
        try:
            self._connector.execute(
                f"INSERT INTO orders ({columns}) VALUES ({placeholders})",
                _order_to_params(order),
            )
        except DatabaseConstraintError as error:
            if self.find_by_id(order.order_id) is not None:
                raise ValueError(
                    f"La commande {order.order_id} existe déjà."
                ) from error
            raise

    def find_by_id(self, order_id: str) -> Order | None:
        row = self._connector.fetch_one(
            f"{_SELECT} WHERE order_id = :order_id", {"order_id": order_id}
        )
        return _row_to_order(row) if row is not None else None

    def save_prediction(self, order_id: str, prediction: Prediction) -> None:
        updated = self._connector.execute(
            "UPDATE orders SET status = :new_status,"
            " predicted_eligible = :predicted_eligible,"
            " eligibility_probability = :eligibility_probability,"
            " model_version = :model_version, predicted_at = :predicted_at"
            " WHERE order_id = :order_id AND status = :expected_status",
            {
                "new_status": OrderStatus.PREDICTED.value,
                "predicted_eligible": prediction.eligible,
                "eligibility_probability": prediction.probability,
                "model_version": prediction.model_version,
                "predicted_at": prediction.predicted_at,
                "order_id": order_id,
                "expected_status": OrderStatus.RECEIVED.value,
            },
        )
        if updated == 0:
            self._raise_update_refused(order_id, "une prédiction")

    def save_real_label(self, order_id: str, real_label: bool) -> None:
        updated = self._connector.execute(
            "UPDATE orders SET status = :new_status, real_label = :real_label"
            " WHERE order_id = :order_id AND status = :expected_status",
            {
                "new_status": OrderStatus.LABELLED.value,
                "real_label": real_label,
                "order_id": order_id,
                "expected_status": OrderStatus.PREDICTED.value,
            },
        )
        if updated == 0:
            self._raise_update_refused(order_id, "le label réel")

    def find_labelled(self, since: datetime, until: datetime) -> list[Order]:
        rows = self._connector.fetch_all(
            f"{_SELECT} WHERE status = :status"
            " AND order_date >= :since AND order_date < :until"
            " ORDER BY order_date, order_id",
            {"status": OrderStatus.LABELLED.value, "since": since, "until": until},
        )
        return [_row_to_order(row) for row in rows]

    def _raise_update_refused(self, order_id: str, what: str) -> None:
        order = self.find_by_id(order_id)
        if order is None:
            raise LookupError(f"La commande {order_id} n'existe pas.")
        raise ValueError(
            f"Commande {order_id} : impossible d'enregistrer {what} "
            f"au statut « {order.status} »."
        )


def _order_to_params(order: Order) -> dict[str, Any]:
    params: dict[str, Any] = {
        column: getattr(order, column) for column in _FEATURE_COLUMNS
    }
    prediction = order.prediction
    params.update(
        status=order.status.value,
        predicted_eligible=prediction.eligible if prediction else None,
        eligibility_probability=prediction.probability if prediction else None,
        model_version=prediction.model_version if prediction else None,
        predicted_at=prediction.predicted_at if prediction else None,
        real_label=order.real_label,
    )
    return params


def _row_to_order(row: Row) -> Order:
    """Normalise les types qui diffèrent selon le moteur (int / bool,
    texte / datetime)."""
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
        weather=row["weather"],
        delivery_zone=row["delivery_zone"],
        customer_type=row["customer_type"],
        status=OrderStatus(row["status"]),
        prediction=prediction,
        real_label=bool(row["real_label"]) if row["real_label"] is not None else None,
    )


def _to_datetime(value: datetime | str) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)
