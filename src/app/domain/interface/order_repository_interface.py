"""Interface : stockage des commandes labellisées, lues par l'entraînement.

Elle déclare les opérations de base sur une commande (`save`, `get`) et l'extraction
du jeu d'entraînement (`get_training_data`). Les implémentations sont dans
`infrastructure/repository/` : en mémoire pour le dev et les tests, MongoDB pour les
commandes de l'ERP (ADR-0009).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.order_entity import OrderEntity


class OrderRepositoryInterface(ABC):
    """Accès aux commandes labellisées, identifiées par `order_id`."""

    @abstractmethod
    def save(self, order: OrderEntity, label: int) -> None:
        """Enregistre une commande et son label (0 ou 1).

        Une commande sans `order_id` est refusée (`ValueError`). Une commande déjà
        enregistrée sous le même `order_id` est remplacée.
        """

    @abstractmethod
    def get(self, order_id: str) -> OrderEntity | None:
        """Retourne la commande, ou `None` si l'identifiant est inconnu."""

    @abstractmethod
    def get_training_data(self) -> tuple[list[OrderEntity], list[int]]:
        """Retourne les commandes et leurs labels (0 ou 1), dans le même ordre."""
