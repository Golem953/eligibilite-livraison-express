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

