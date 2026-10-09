from abc import ABC, abstractmethod

from domain.entities.order import Order
from domain.value_objects.prediction import Prediction


class OrderRepositoryInterface(ABC):
    """Port de sortie : persistance des commandes (ADR-0001).

    Décrit ce dont l'application a besoin, sans rien supposer de la technique
    de stockage.
    """

    @abstractmethod
    def save(self, order: Order) -> None:
        """Enregistre une nouvelle commande.

        Lève ValueError si l'identifiant existe déjà.
        """

    @abstractmethod
    def save_all(self, orders: list[Order]) -> None:
        """Enregistre plusieurs commandes d'un coup (tout ou rien).

        Lève ValueError si l'une d'elles est refusée.
        """

    @abstractmethod
    def delete_all(self) -> None:
        """Supprime toutes les commandes. Réservé aux outils de développement."""

    @abstractmethod
    def find_by_id(self, order_id: str) -> Order | None:
        """Renvoie la commande, ou None si elle n'existe pas."""

    @abstractmethod
    def save_prediction(self, order_id: str, prediction: Prediction) -> None:
        """Passe la commande de « reçue » à « prédite ».

        Lève LookupError si la commande n'existe pas, ValueError si son statut
        ne le permet pas.
        """

    @abstractmethod
    def save_real_label(self, order_id: str, real_label: bool) -> None:
        """Passe la commande de « prédite » à « labellisée ».

        Lève LookupError si la commande n'existe pas, ValueError si son statut
        ne le permet pas.
        """
