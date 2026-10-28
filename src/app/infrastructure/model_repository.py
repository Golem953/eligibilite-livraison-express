"""Abstraction : où l'application range le modèle entraîné.

Trois besoins distincts se cachent derrière cette abstraction, et les confondre est
l'erreur classique :

1. **Écrire** le modèle et ses métadonnées à l'entraînement (cellule 41 du notebook :
   `joblib.dump`, `metrics.json`, `features.json`) ;
2. **Lire** un modèle déjà entraîné au démarrage de l'API (cellule 43 :
   `joblib.load`) — c'est ce qui distingue un service de production d'un notebook ;
3. **Savoir quelle version est en service** et l'exposer (cellule 55 : la model card,
   endpoint `GET /v1/model`, vu en prochaine séance).

Un service de prédiction ne doit jamais réentraîner un modèle au démarrage : il charge
un artefact produit ailleurs. Cette séparation entraînement / service est l'un des
fondamentaux de l'industrialisation, et elle se voit ici.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.entities import ModelEntity


class ModelRepository(ABC):
    """Stockage des artefacts du modèle et de ses métadonnées.

    Contrats attendus de toute implémentation :

    - `save` écrit le modèle **et** les métadonnées de façon cohérente entre elles
      (cellule 41 du notebook écrit trois fichiers : les trois doivent être cohérents)
    - `load` doit être tolérant à l'absence d'artefact : l'API doit démarrer quand même
      et signaler l'indisponibilité sur `/health/ready`, pas exploser au démarrage
    - les identifiants de version sont des chaînes telles que "1.0.0".
    """

    @abstractmethod
    def save(self, model: object, model_card: ModelEntity) -> None:
        """Enregistrement des artefacts du modèle et de ses métadonnées.

        Notebook: cellule 41 (joblib.dump + metrics.json + features.json).
        """
        raise NotImplementedError # L'implémentation se fait dans le dossier infrastructure/

    @abstractmethod
    def load(self, version: str) -> object | None:
        """Retourne le modèle ayant la version #version.
        Retourn None si aucun modèle n'a pu être chargé.

        Notebook: cellule 43 (joblib.load).


        """
        raise NotImplementedError # L'implémentation se fait dans le dossier infrastructure/
