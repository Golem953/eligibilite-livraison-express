from __future__ import annotations

from app.domain.entities.model_entity import ModelEntity
from app.domain.interface.model_repository_interface import ModelRepositoryInterface


class FakeModelRepository(ModelRepositoryInterface):
    """Dépôt de modèle factice : garde le modèle en mémoire et compte les enregistrements."""

    def __init__(self, model: object | None = None):
        self.model = model
        self.model_card: ModelEntity | None = None
        self.saves = 0

    def save(self, model: object, model_card: ModelEntity) -> None:
        self.model = model
        self.model_card = model_card
        self.saves += 1

    def load(self) -> object | None:
        return self.model
