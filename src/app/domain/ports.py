"""Ports : ce dont l'application a besoin, sans dire comment c'est fait.

Les implémentations sont dans `infrastructure/`. Chaque interface ne déclare que ce
que ses utilisateurs appellent réellement : une méthode s'ajoute le jour où un
utilisateur en a besoin (par exemple l'enregistrement des commandes reçues par
l'API, prévu par l'ADR-0001).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .entities import ModelEntity, OrderEntity


class OrderRepository(ABC):
    """Source des commandes labellisées, lue par l'entraînement."""

    @abstractmethod
    def get_training_data(self) -> tuple[list[OrderEntity], list[int]]:
        """Retourne les commandes et leurs labels (0 ou 1), dans le même ordre."""


class ModelRepository(ABC):
    """Stockage du modèle entraîné et de sa fiche (model card).

    `load` est tolérant à l'absence de modèle : il renvoie `None`, pour que l'API
    démarre quand même et signale l'indisponibilité sur `/health/ready`.
    """

    @abstractmethod
    def save(self, model: object, model_card: ModelEntity) -> None:
        """Enregistre le modèle et sa fiche, de façon cohérente entre eux."""

    @abstractmethod
    def load(self) -> object | None:
        """Retourne le modèle enregistré, ou `None` s'il n'y en a pas."""


class ExperimentTracker(ABC):
    """Suivi des entraînements (paramètres, métriques, modèle)."""

    @abstractmethod
    def log_run(
        self,
        run_name: str,
        params: dict[str, object],
        metrics: dict[str, float],
        model: object,
    ) -> str:
        """Enregistre un entraînement et retourne son identifiant."""
