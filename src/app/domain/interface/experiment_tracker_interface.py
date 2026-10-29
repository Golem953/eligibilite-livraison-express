"""Interface : suivi des entraînements (paramètres, métriques, modèle).

Implémentée par `MlflowTracker` (`infrastructure/implementation/mlflow_tracker.py`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExperimentTrackerInterface(ABC):
    """Enregistre chaque entraînement."""

    @abstractmethod
    def log_run(
        self,
        run_name: str,
        params: dict[str, object],
        metrics: dict[str, float],
        model: object,
    ) -> str:
        """Enregistre un entraînement et retourne son identifiant."""
