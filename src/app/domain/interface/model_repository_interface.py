"""Interface : stockage du modèle entraîné et de sa fiche (model card).

Les implémentations sont dans `infrastructure/repository/`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.model_entity import ModelEntity


class ModelRepositoryInterface(ABC):
    """Enregistrement et chargement du modèle.

    `load` est tolérant à l'absence de modèle : il renvoie `None`, pour que l'API
    démarre quand même et signale l'indisponibilité sur `/health/ready`.
    """

    @abstractmethod
    def save(self, model: object, model_card: ModelEntity) -> None:
        """Enregistre le modèle et sa fiche, de façon cohérente entre eux."""

    @abstractmethod
    def load(self) -> object | None:
        """Retourne le modèle enregistré, ou `None` s'il n'y en a pas."""
