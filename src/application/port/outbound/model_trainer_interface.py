from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from domain.entities.order import Order


@dataclass(frozen=True)
class TrainedModel:
    """Modèle entraîné, opaque pour l'application (ex. pipeline scikit-learn)."""

    model: Any
    metrics: dict[str, float]
    params: dict[str, Any]
    # Quelques lignes d'entrée, pour enregistrer la signature du modèle.
    input_example: Any = None


class ModelTrainerInterface(ABC):
    """Port de sortie : entraîne et évalue un modèle à partir de commandes
    labellisées (ADR-0003)."""

    @abstractmethod
    def train(self, orders: list[Order]) -> TrainedModel:
        """Lève ValueError si les commandes ne permettent pas d'entraîner."""
