"""`OrderRepositoryInterface` de développement : les commandes dans un dictionnaire en mémoire.

Il peut recevoir ses commandes à la construction : il ne sait pas d'où elles viennent
(générateur de données synthétiques en dev, jeu de test dans les tests). Elles passent
par `save`, comme celles ajoutées ensuite.

Limites, à connaître : les données sont perdues au redémarrage et ne sont pas
partagées entre deux processus (ADR-0001). Très bien pour le dev et les tests,
**inacceptable** en production.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...domain.entities.order_entity import OrderEntity
from ...domain.interface.order_repository_interface import OrderRepositoryInterface


class InMemoryOrderRepository(OrderRepositoryInterface):
    """Commandes labellisées gardées en mémoire, indexées par `order_id`."""

    def __init__(self, orders: Sequence[OrderEntity] = (), labels: Sequence[int] = ()):
        if len(orders) != len(labels):
            raise ValueError("Le nombre de commandes doit correspondre au nombre de labels")
        self._orders: dict[str, OrderEntity] = {}
        self._labels: dict[str, int] = {}
        for order, label in zip(orders, labels):
            self.save(order, label)

    def save(self, order: OrderEntity, label: int) -> None:
        if order.order_id is None:
            raise ValueError("Chaque commande doit avoir un order_id")
        self._orders[order.order_id] = order
        self._labels[order.order_id] = label

    def get(self, order_id: str) -> OrderEntity | None:
        return self._orders.get(order_id)

    def get_training_data(self) -> tuple[list[OrderEntity], list[int]]:
        orders = list(self._orders.values())
        return orders, [self._labels[order.order_id] for order in orders]
