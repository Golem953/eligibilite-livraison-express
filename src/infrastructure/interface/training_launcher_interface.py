from abc import ABC, abstractmethod


class TrainingLauncherInterface(ABC):
    """Démarre l'outil d'entraînement hors du processus de l'API (ADR-0003)."""

    @abstractmethod
    def start(self) -> int:
        """Démarre un entraînement et renvoie l'identifiant du processus.

        Lève RuntimeError si un entraînement est déjà en cours.
        """
