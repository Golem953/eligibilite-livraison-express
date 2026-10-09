from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

Params = Mapping[str, Any]
Row = dict[str, Any]


class DatabaseConstraintError(Exception):
    """La base a refusé une donnée : contrainte (clé, CHECK, NOT NULL) ou type."""


class DatabaseConnectorInterface(ABC):
    @abstractmethod
    def create_schema(self) -> None:
        """Crée les tables si elles n'existent pas (script propre au moteur)."""

    @abstractmethod
    def execute(self, query: str, params: Params | None = None) -> int:
        """Exécute un INSERT / UPDATE / DELETE et renvoie le nombre de lignes
        touchées."""

    @abstractmethod
    def fetch_one(self, query: str, params: Params | None = None) -> Row | None:
        """Exécute un SELECT et renvoie la première ligne, ou None."""

    @abstractmethod
    def fetch_all(self, query: str, params: Params | None = None) -> list[Row]:
        """Exécute un SELECT et renvoie toutes les lignes."""
