from domain.interface.order_id_generator_interface import OrderIdGeneratorInterface
from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
)


class SqlOrderIdGenerator(OrderIdGeneratorInterface):
    """Identifiants CMD-000001, CMD-000002… tirés d'un compteur auto-incrémenté
    de la base (table order_id_sequence). Le SQL est le même pour tous les
    moteurs (ADR-0001)."""

    def __init__(self, connector: DatabaseConnectorInterface) -> None:
        self._connector = connector

    def next_id(self) -> str:
        row = self._connector.fetch_one(
            "INSERT INTO order_id_sequence DEFAULT VALUES RETURNING id"
        )
        if row is None:
            raise RuntimeError("La base n'a pas renvoyé de numéro de commande.")
        return f"CMD-{row['id']:06d}"
