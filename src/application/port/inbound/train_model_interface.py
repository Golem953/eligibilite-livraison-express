from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingReport:
    model_version: str
    order_count: int
    metrics: dict[str, float]
    promoted: bool
    # Scores qui désignent le champion, par ordre de priorité.
    champion_metrics: list[str]
    previous_champion_scores: dict[str, float] | None


class TrainModelInterface(ABC):
    """Port d'entrée : use case « réentraîner le modèle » (ADR-0003)."""

    @abstractmethod
    def train(self) -> TrainingReport:
        """Entraîne sur toutes les commandes labellisées, enregistre la nouvelle
        version et la désigne champion si elle fait mieux.

        Lève ValueError s'il n'y a rien à entraîner.
        """
