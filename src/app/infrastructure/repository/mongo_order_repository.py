"""`OrderRepositoryInterface` des commandes de l'ERP : la collection `orders` de MongoDB.

L'entraînement lit les commandes que l'ETL de l'ERP écrit dans MongoDB (ADR-0009).
Chaque document contient les variables de `OrderEntity` et le label `express_eligible`.

MongoDB n'impose aucun schéma : chaque document est contrôlé à la lecture. Pour
l'entraînement, un document sans label est ignoré, et un document invalide (champ
absent, `null` ou de mauvais type) est écarté et compté dans les logs.

`save` remplace la commande de même `order_id`. Il sert à alimenter une base de dev
ou de CI : en prod, le compte de l'entraînement est en lecture seule (ADR-0009) et
MongoDB refuse l'écriture.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any, get_type_hints

from ...domain.entities.order_entity import OrderEntity
from ...domain.interface.order_repository_interface import OrderRepositoryInterface

if TYPE_CHECKING:
    from pymongo.collection import Collection

logger = logging.getLogger(__name__)

COLLECTION_NAME = "orders"
# Même nom que la cible du modèle (`TARGET_COLUMN`) et que la colonne du générateur.
LABEL_FIELD = "express_eligible"

# Type attendu de chaque variable de la commande, lu sur `OrderEntity`.
_FIELD_TYPES = {
    field.name: get_type_hints(OrderEntity)[field.name]
    for field in dataclasses.fields(OrderEntity)
    if field.name != "order_id"
}


class MongoOrderRepository(OrderRepositoryInterface):
    """Commandes labellisées lues dans une collection MongoDB, indexées par `order_id`."""

    def __init__(self, collection: Collection):
        self._collection = collection

    @classmethod
    def from_url(cls, url: str) -> MongoOrderRepository:
        """Se connecte à la base nommée dans l'URL (`mongodb://hôte:27017/livraison_express`)."""
        # Import local : seule cette implémentation dépend de pymongo.
        from pymongo import MongoClient

        database = MongoClient(url).get_default_database()
        return cls(database[COLLECTION_NAME])

    def save(self, order: OrderEntity, label: int) -> None:
        if order.order_id is None:
            raise ValueError("Chaque commande doit avoir un order_id")
        document = {**dataclasses.asdict(order), LABEL_FIELD: label}
        self._collection.replace_one({"order_id": order.order_id}, document, upsert=True)

    def get(self, order_id: str) -> OrderEntity | None:
        document = self._collection.find_one({"order_id": order_id}, {"_id": 0})
        return None if document is None else _to_order(document)

    def get_training_data(self) -> tuple[list[OrderEntity], list[int]]:
        documents = self._collection.find(
            {LABEL_FIELD: {"$in": [0, 1]}}, {"_id": 0}
        ).sort("order_id", 1)
        orders: list[OrderEntity] = []
        labels: list[int] = []
        rejected = 0
        for document in documents:
            try:
                orders.append(_to_order(document))
            except ValueError as error:
                rejected += 1
                logger.debug("Commande écartée (%s) : %s", document.get("order_id"), error)
                continue
            labels.append(int(document[LABEL_FIELD]))
        if rejected:
            logger.warning("%d commande(s) invalide(s) écartée(s) de l'entraînement", rejected)
        return orders, labels


def _to_order(document: dict[str, Any]) -> OrderEntity:
    """Convertit un document MongoDB en `OrderEntity`, ou lève `ValueError`."""
    values: dict[str, Any] = {"order_id": str(document["order_id"])}
    for name, expected_type in _FIELD_TYPES.items():
        value = document.get(name)
        if value is None:
            raise ValueError(f"champ {name} absent")
        if expected_type is str and not isinstance(value, str):
            raise ValueError(f"champ {name} : texte attendu")
        if expected_type is not str and not isinstance(value, (int, float)):
            raise ValueError(f"champ {name} : nombre attendu")
        if expected_type is int and value != int(value):
            raise ValueError(f"champ {name} : entier attendu")
        values[name] = expected_type(value)
    return OrderEntity(**values)
