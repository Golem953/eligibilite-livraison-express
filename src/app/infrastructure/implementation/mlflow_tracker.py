"""`ExperimentTrackerInterface` basée sur MLflow.

Seul module de l'application qui importe MLflow : le reste du code ne connaît que
l'interface `ExperimentTrackerInterface`. L'emplacement des runs vient de la variable
d'environnement `MLFLOW_TRACKING_URI`, lue par MLflow lui-même.
"""

from __future__ import annotations

import mlflow
import mlflow.sklearn

from ...domain.interface.experiment_tracker_interface import ExperimentTrackerInterface


class MlflowTracker(ExperimentTrackerInterface):
    """Enregistre chaque entraînement comme un run MLflow."""

    def __init__(self, experiment_name: str):
        self._experiment_name = experiment_name

    def log_run(
        self,
        run_name: str,
        params: dict[str, object],
        metrics: dict[str, float],
        model: object,
    ) -> str:
        mlflow.set_experiment(self._experiment_name)
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.log_params(params)
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(model, name="model", skops_trusted_types=["numpy.dtype"])
            return run.info.run_id
