from dataclasses import dataclass
from datetime import UTC, datetime

import mlflow
import mlflow.sklearn
from mlflow import MlflowClient

from config.settings import MODEL_ALIAS, REGISTERED_MODEL_NAME


@dataclass(frozen=True)
class LoadedModel:
    model: object
    version: str
    run_id: str
    metrics: dict
    trained_at: datetime


class ModelRegistry:
    """Registre MLflow : la version servie par l'API porte l'alias MODEL_ALIAS."""

    def __init__(
        self, tracking_uri, model_name=REGISTERED_MODEL_NAME, alias=MODEL_ALIAS
    ):
        mlflow.set_tracking_uri(tracking_uri)
        self.client = MlflowClient(tracking_uri)
        self.model_name = model_name
        self.alias = alias

    def register(self, run_id):
        """Inscrit le modèle du run et lui donne l'alias : il devient servi."""
        model_uri = f"runs:/{run_id}/model"
        version = mlflow.register_model(model_uri, self.model_name).version
        self.client.set_registered_model_alias(self.model_name, self.alias, version)
        return version

    def load_champion(self):
        model_version = self.client.get_model_version_by_alias(
            self.model_name, self.alias
        )
        # Chargement par numéro de version : l'alias peut bouger entre-temps.
        model = mlflow.sklearn.load_model(
            f"models:/{self.model_name}/{model_version.version}"
        )
        run = self.client.get_run(model_version.run_id)
        return LoadedModel(
            model=model,
            version=str(model_version.version),
            run_id=model_version.run_id,
            metrics=dict(run.data.metrics),
            trained_at=datetime.fromtimestamp(run.info.start_time / 1000, tz=UTC),
        )
