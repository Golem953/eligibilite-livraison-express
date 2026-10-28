"""`OrderRepository` de développement : un dictionnaire en mémoire.

Implémentation de l'abstraction `OrderRepository`.

Ce fichier sert trois usages :

1. faire tourner l'application et les tests sans installer de base de données
2. montrer à quoi ressemble une implémentation : les dépendances injectées au
   constructeur, les erreurs du domaine, rien de spécifique à une technologie
3. servir de point de comparaison quand vous écrirez la vôtre.

Limites, à connaître : les données sont perdues au redémarrage,
rien n'est partagé entre deux processus, et la recherche est linéaire.
C'est très bien pour un test unitaire, **inacceptable** en production.
"""

from __future__ import annotations

import logging

from ....config import Settings
from ....domain.entities import OrderEntity
from ...order_repository import OrderRepository
from .order_generator import generate_labeled_orders

logger = logging.getLogger(__name__)


class InMemoryOrderRepository(OrderRepository):
    """Enregistre les commandes dans un dictionnaire en mémoire."""

    def __init__(self, generated: bool):
        self._orders: dict[str, OrderEntity] = {}
        self._labels: dict[str, int] = {}
        if generated:
            orders, labels = generate_labeled_orders(random_state=Settings().random_seed)
            for order, label in zip(orders, labels):
                self._orders[order.order_id] = order
                self._labels[order.order_id] = label
            logger.info("Jeu de données généré en mémoire (commandes=%d)", len(self._orders))

    def save(self, order: OrderEntity) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> OrderEntity | None:
        return self._orders.get(order_id)

    def get_all(self) -> list[OrderEntity]:
        return list(self._orders.values())

    def get_training_data(self) -> tuple[list[OrderEntity], list[int]]:
        """Retourner les entités et leurs labels dans le même ordre."""
        orders = self.get_all()
        labels = [self._labels[order.order_id] for order in orders]
        logger.debug("Données extraites du dépôt (commandes=%d)", len(orders))
        return orders, labels

    def count(self) -> int:
        return len(self._orders)

    def clear(self) -> None:
        self._orders.clear()
        self._labels.clear()
