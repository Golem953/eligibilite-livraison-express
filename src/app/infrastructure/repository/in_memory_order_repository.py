"""`OrderRepositoryInterface` de développement : les commandes dans un dictionnaire en mémoire.

Il reçoit ses commandes à la construction : il ne sait pas d'où elles viennent
(générateur de données synthétiques en dev, jeu de test dans les tests).

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

    def __init__(self, orders: Sequence[OrderEntity], labels: Sequence[int]):
        if len(orders) != len(labels):
            raise ValueError("Le nombre de commandes doit correspondre au nombre de labels")
        if any(order.order_id is None for order in orders):
            raise ValueError("Chaque commande doit avoir un order_id")
        self._orders = {order.order_id: order for order in orders}
        self._labels = {order.order_id: label for order, label in zip(orders, labels)}

    def get_training_data(self) -> tuple[list[OrderEntity], list[int]]:
        orders = list(self._orders.values())
        return orders, [self._labels[order.order_id] for order in orders]
