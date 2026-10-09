from abc import ABC, abstractmethod
from typing import Any

from domain.entities.order import Order


class OrderServiceInterface(ABC):
    """Port d'entrée : collecte et lecture des commandes."""

    @abstractmethod
    def create_order(self, order_id: str | None = None, **features: Any) -> Order:
        """Crée et enregistre une commande au statut « reçue ».

        `features` : les variables de la commande (hour, distance_km…).
        Sans order_id, un identifiant CMD-xxxxxx est attribué.
        Lève OrderAlreadyExistsError si l'identifiant est déjà pris, ValueError
        si une valeur est invalide.
        """

    @abstractmethod
    def get_order(self, order_id: str) -> Order | None:
        """Renvoie la commande, ou None si elle n'existe pas."""
