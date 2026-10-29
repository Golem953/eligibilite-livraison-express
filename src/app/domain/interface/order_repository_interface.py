"""Interface : source des commandes labellisées, lue par l'entraînement.

Elle ne déclare que ce que ses utilisateurs appellent : une méthode s'ajoute le jour
où un utilisateur en a besoin (par exemple l'enregistrement des commandes reçues par
l'API, prévu par l'ADR-0001). Les implémentations sont dans `infrastructure/repository/`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.order_entity import OrderEntity


class OrderRepositoryInterface(ABC):
    """Accès aux commandes labellisées."""

    @abstractmethod
    def get_training_data(self) -> tuple[list[OrderEntity], list[int]]:
        """Retourne les commandes et leurs labels (0 ou 1), dans le même ordre."""
