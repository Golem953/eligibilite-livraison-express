"""Composition root : le seul endroit qui choisit les adapters.

Les valeurs viennent de la configuration (infrastructure/config/settings.py) :
le stockage des commandes est choisi par le préfixe de DATABASE_URL (ADR-0001).

Ajouter un moteur = écrire sa fabrique et l'enregistrer dans _REPOSITORY_FACTORIES :
- moteur SQL (MariaDB, MySQL…) : un connecteur implémentant
  DatabaseConnectorInterface, passé à SqlOrderRepository ;
- moteur non SQL (MongoDB…) : un nouveau OrderRepositoryInterface, sans connecteur SQL.
"""

from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING

from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from infrastructure.config.settings import get_settings
from infrastructure.interface.training_launcher_interface import (
    TrainingLauncherInterface,
)
from infrastructure.repository.sql_order_repository import SqlOrderRepository

if TYPE_CHECKING:
    from application.port.inbound.predict_eligibility_interface import (
        PredictEligibilityInterface,
    )
    from application.port.outbound.eligibility_predictor_interface import (
        EligibilityPredictorInterface,
    )
    from application.services.train_service import TrainService


def _sqlite_order_repository(url: str) -> OrderRepositoryInterface:
    from infrastructure.repository.sqlite_connector import SqliteConnector

    connector = SqliteConnector(url.removeprefix("sqlite:///"))
    connector.create_schema()
    return SqlOrderRepository(connector)


def _postgres_order_repository(url: str) -> OrderRepositoryInterface:
    # Import local : le pilote PostgreSQL n'est chargé que s'il sert.
    from infrastructure.repository.postgres_connector import PostgresConnector

    connector = PostgresConnector(url)
    connector.create_schema()
    return SqlOrderRepository(connector)


# Préfixe de DATABASE_URL (avant « :// ») → fabrique du repository.
_REPOSITORY_FACTORIES: dict[str, Callable[[str], OrderRepositoryInterface]] = {
    "sqlite": _sqlite_order_repository,
    "postgresql": _postgres_order_repository,
    "postgres": _postgres_order_repository,
}


def build_order_repository(database_url: str) -> OrderRepositoryInterface:
    scheme = database_url.split("://", 1)[0]
    factory = _REPOSITORY_FACTORIES.get(scheme)
    if factory is None:
        raise ValueError(
            f"Moteur de base de données non supporté : « {scheme} ». "
            f"Moteurs disponibles : {sorted(_REPOSITORY_FACTORIES)}."
        )
    return factory(database_url)


@lru_cache
def get_order_repository() -> OrderRepositoryInterface:
    """À injecter dans les routes avec `Depends(get_order_repository)`."""
    return build_order_repository(get_settings().database_url)


@lru_cache
def get_training_launcher() -> TrainingLauncherInterface:
    """Une seule instance : elle sait si un entraînement est déjà en cours."""
    from infrastructure.ml.subprocess_training_launcher import (
        SubprocessTrainingLauncher,
    )

    return SubprocessTrainingLauncher()


def get_train_service() -> TrainService:
    """Utilisé par la CLI d'entraînement uniquement. Imports locaux : l'API ne
    charge jamais le code d'entraînement (ADR-0003)."""
    from application.services.train_service import TrainService
    from infrastructure.config.training_config import get_training_config
    from infrastructure.ml.sklearn_model_trainer import SklearnModelTrainer
    from infrastructure.repository.mlflow_model_repository import (
        MlflowModelRepository,
    )

    config = get_training_config()
    return TrainService(
        orders=get_order_repository(),
        trainer=SklearnModelTrainer(config),
        models=MlflowModelRepository(
            get_settings().mlflow_tracking_uri, config.promotion.alias
        ),
        champion_metrics=config.promotion.metrics,
    )


@lru_cache
def get_eligibility_predictor() -> EligibilityPredictorInterface:
    """Une seule instance : elle garde le modèle champion en mémoire."""
    from infrastructure.config.training_config import get_training_config
    from infrastructure.ml.predict.mlflow_eligibility_predictor import (
        MlflowEligibilityPredictor,
    )

    config = get_training_config()
    return MlflowEligibilityPredictor(
        tracking_uri=get_settings().mlflow_tracking_uri,
        champion_alias=config.promotion.alias,
        feature_columns=config.features.feature_columns,
        threshold=config.decision.threshold,
    )


def get_predict_service() -> PredictEligibilityInterface:
    """À injecter dans les routes avec `Depends(get_predict_service)`."""
    from application.services.predict_service import PredictService

    return PredictService(
        orders=get_order_repository(), predictor=get_eligibility_predictor()
    )
