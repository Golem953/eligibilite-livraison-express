import mlflow
import mlflow.sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from application.port.outbound.model_repository_interface import (
    ModelRepositoryInterface,
)
from application.port.outbound.model_trainer_interface import TrainedModel

EXPERIMENT_NAME = "livraison-express"
REGISTERED_MODEL_NAME = "eligibilite-express"
SKOPS_TRUSTED_TYPES = ["numpy.dtype"]


class MlflowModelRepository(ModelRepositoryInterface):
    """Adapter MLflow du port ModelRepositoryInterface (ADR-0002) : un run par
    entraînement, une nouvelle version dans le Model Registry, et un alias
    (« champion ») sur la version à utiliser en production."""

    def __init__(self, tracking_uri: str, champion_alias: str) -> None:
        self._tracking_uri = tracking_uri
        self._champion_alias = champion_alias
        self._client = MlflowClient(tracking_uri)

    def save(self, trained_model: TrainedModel) -> str:
        mlflow.set_tracking_uri(self._tracking_uri)
        mlflow.set_experiment(EXPERIMENT_NAME)
        with mlflow.start_run():
            mlflow.log_params(trained_model.params)
            mlflow.log_metrics(trained_model.metrics)
            model_info = mlflow.sklearn.log_model(
                trained_model.model,
                name="model",
                registered_model_name=REGISTERED_MODEL_NAME,
                input_example=trained_model.input_example,
                # Format skops (défaut MLflow 3) : seuls les types déclarés sûrs
                # sont acceptés au rechargement, contrairement à pickle.
                skops_trusted_types=SKOPS_TRUSTED_TYPES,
            )
        return str(model_info.registered_model_version)

    def get_champion_metrics(self) -> dict[str, float] | None:
        try:
            champion = self._client.get_model_version_by_alias(
                REGISTERED_MODEL_NAME, self._champion_alias
            )
        except MlflowException:  # pas encore de modèle ou pas encore de champion
            return None
        return self._client.get_run(champion.run_id).data.metrics

    def promote(self, version: str) -> None:
        self._client.set_registered_model_alias(
            REGISTERED_MODEL_NAME, self._champion_alias, version
        )
