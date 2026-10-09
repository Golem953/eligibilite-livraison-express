from abc import ABC, abstractmethod

from domain.entities.order import Order
from domain.value_objects.prediction import Prediction


class PredictEligibilityInterface(ABC):
    """Port d'entrée : use case « prédire l'éligibilité d'une commande »."""

    @abstractmethod
    def predict(self, order: Order) -> Prediction:
        """Prédit puis enregistre la commande au statut « prédite ».

        Lève LookupError s'il n'y a pas de modèle champion, ValueError si la
        commande est refusée (identifiant déjà utilisé…).
        """

    @abstractmethod
    def predict_batch(self, orders: list[Order]) -> list[Prediction]:
        """Même chose pour plusieurs commandes, enregistrées en une fois."""
