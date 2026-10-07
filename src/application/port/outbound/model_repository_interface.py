from abc import ABC, abstractmethod

from application.port.outbound.model_trainer_interface import TrainedModel


class ModelRepositoryInterface(ABC):
    """Port de sortie : stockage des versions du modèle (ADR-0002)."""

    @abstractmethod
    def save(self, trained_model: TrainedModel) -> str:
        """Enregistre une nouvelle version du modèle et renvoie son numéro."""

    @abstractmethod
    def get_champion_metrics(self) -> dict[str, float] | None:
        """Métriques de la version champion, ou None s'il n'y en a pas encore."""

    @abstractmethod
    def promote(self, version: str) -> None:
        """Fait de cette version le nouveau champion."""
