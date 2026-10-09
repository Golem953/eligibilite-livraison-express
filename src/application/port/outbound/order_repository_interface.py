from abc import ABC, abstractmethod

from domain.entities.order import Order


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
    def get_order_by_id(self, order_id: str) -> Order | None:
        """Renvoie la commande, ou None si aucune commande n'a cet identifiant."""

    @abstractmethod
    def find_labelled(self) -> list[Order]:
        """Commandes dont le label réel est connu : le jeu d'entraînement.

        Jamais les prédictions seules, pour éviter la boucle de rétroaction
        (ADR-0001).
        """
