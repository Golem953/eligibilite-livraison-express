from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

Params = Mapping[str, Any]
Row = dict[str, Any]


class DatabaseConstraintError(Exception):
    """La base a refusé une donnée : contrainte (clé, CHECK, NOT NULL) ou type."""


class DatabaseConnectorInterface(ABC):
    """Interface technique d'accès à une base SQL, une implémentation par moteur.

    Ce n'est pas un port de l'application : seuls les repositories SQL l'utilisent.
    Changer de moteur revient à changer de connecteur dans la composition root.

    Conventions communes à tous les connecteurs :
    - paramètres nommés au format `:nom`, jamais de valeur écrite dans la requête ;
    - chaque appel s'exécute dans sa propre transaction (commit, ou rollback
      en cas d'erreur) ;
    - les dates passées en paramètre doivent avoir un fuseau horaire ;
    - toute donnée refusée par la base lève DatabaseConstraintError.

    Les types renvoyés peuvent différer selon le moteur (un booléen est un int
    en SQLite, une date est un texte ISO 8601) : le repository les normalise.
    """

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
