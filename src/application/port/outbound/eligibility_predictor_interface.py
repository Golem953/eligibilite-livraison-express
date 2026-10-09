from abc import ABC, abstractmethod

from domain.entities.order import Order
from domain.value_objects.prediction import Prediction


class EligibilityPredictorInterface(ABC):
    """Port de sortie : le modèle champion qui prédit l'éligibilité."""

    @abstractmethod
    def predict(self, order: Order) -> Prediction:
        """Lève LookupError s'il n'y a pas encore de modèle champion."""

    @abstractmethod
    def predict_batch(self, orders: list[Order]) -> list[Prediction]:
        """Une prédiction par commande, dans le même ordre.

        Lève LookupError s'il n'y a pas encore de modèle champion.
        """
