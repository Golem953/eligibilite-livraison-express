"""Abstraction : où l'application range les commandes qu'elle collecte.

Les implémentations sont dans `infrastructure/`.

Le besoin est simple et la réponse technique ne l'est pas : une commande est écrite
une fois et lue potentiellement plusieurs fois (page de surveillance, ré-exécution du
batch, analyse après incident). Le choix du support (PostgreSQL, Redis, SQLite,
fichiers, API existante) dépend de ce que vous avez, de la fréquence de lecture,
de la durée de conservation et de vos contraintes d'exploitation.

Ne partez pas du choix : partez du besoin.

Ce que la couche application exige d'un support de stockage est listé ci-dessous.
Toute solution qui ne tient pas ces méthodes ne convient pas, quelle qu'elle soit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.entities import OrderEntity


class OrderRepository(ABC):
    """Persistance des commandes.

    Contrat attendu par la couche application :

    - `save` enregistre la même commande sans créer de doublon (grâce à order_id)
    - `get` renvoie `None` pour un identifiant inconnu, et ne lève pas d'exception
    - les noms d'erreurs à lever sont ceux de `domain/exceptions.py`, pas ceux de la
      bibliothèque de stockage utilisée (PostgreSQL, Redis...) : l'application ne
      doit pas connaître l'infrastructure. (pour des questions de sécurités)
    """

    @abstractmethod
    def save(self, order: OrderEntity) -> None:
        """Sauvegarde d'une commande."""
        raise NotImplementedError # L'implémentation se fait dans le dossier infrastructure/

    @abstractmethod
    def get(self, order_id: str) -> OrderEntity | None:
        """Retourne la commande ayant l'identifiant #order_id.
        Retourne None si aucune commande trouvée.
        """
        raise NotImplementedError # L'implémentation se fait dans le dossier infrastructure/

    @abstractmethod
    def get_all(self) -> list[OrderEntity]:
        """Retourne l'ensemble des commandes."""
        raise NotImplementedError # L'implémentation se fait dans le dossier infrastructure/

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre de commandes."""
        raise NotImplementedError # L'implémentation se fait dans le dossier infrastructure/
