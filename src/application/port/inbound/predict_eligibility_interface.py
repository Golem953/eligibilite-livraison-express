from abc import ABC, abstractmethod
from typing import Any

from domain.entities.order import Order


class PredictEligibilityInterface(ABC):
    """Port d'entrée : use case « prédire l'éligibilité d'une commande »."""

    @abstractmethod
    def predict(self, order_id: str | None = None, **features: Any) -> Order:
        """Prédit avec le modèle champion, puis enregistre la commande au statut
        « prédite » et la renvoie avec sa prédiction.

        `features` : les variables de la commande (hour, distance_km…).
        Lève LookupError s'il n'y a pas de modèle champion,
        OrderAlreadyExistsError si l'identifiant est déjà pris, ValueError si une
        valeur est invalide.
        """
