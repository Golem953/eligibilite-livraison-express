"""Composition root : le seul endroit qui choisit les adapters.

Configuration par variables d'environnement (voir .env.example) :
- DATABASE_URL : moteur de base choisi par son préfixe (ADR-0001)
    sqlite:///data/commandes.db
    postgresql://commandes_user:…@db:5432/commandes
- MLFLOW_TRACKING_URI : serveur MLflow (ADR-0002), http://mlflow:5000 en Docker.

Les imports d'adapters sont locaux : chaque point d'entrée ne charge que ce qu'il
utilise. L'API de prédiction ne charge jamais le code d'entraînement, et la CLI
d'entraînement ne charge jamais FastAPI (ADR-0003).
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from application.port.inbound.order_service_interface import OrderServiceInterface
from application.services.order_service import OrderService
from domain.factory.order_factory import OrderFactory
from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
)
from infrastructure.repository.sql_order_id_generator import SqlOrderIdGenerator
from infrastructure.repository.sql_order_repository import SqlOrderRepository

if TYPE_CHECKING:
    from application.port.inbound.predict_eligibility_interface import (
        PredictEligibilityInterface,
    )
    from application.port.inbound.train_model_interface import TrainModelInterface
    from infrastructure.interface.training_launcher_interface import (
        TrainingLauncherInterface,
    )

DEFAULT_DATABASE_URL = "sqlite:///data/commandes.db"
# Sans serveur MLflow (dev local hors Docker) : fichier SQLite séparé (ADR-0002).
DEFAULT_MLFLOW_TRACKING_URI = "sqlite:///data/mlflow.db"
# Racine du dépôt en dev (src/infrastructure/adapter/dependency_injection/…).
# Dans l'image Docker, MIGRATIONS_DIR est fixé par le Dockerfile.
DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations"


def build_connector(database_url: str) -> DatabaseConnectorInterface:
    """Connecteur du moteur désigné par l'URL, schéma à jour."""
    migrations_dir = Path(os.environ.get("MIGRATIONS_DIR", DEFAULT_MIGRATIONS_DIR))
    engine = database_url.split("://", 1)[0]
    if engine == "sqlite":
        from infrastructure.repository.sqlite_connector import SqliteConnector

        connector: DatabaseConnectorInterface = SqliteConnector(
            database_url.removeprefix("sqlite:///"), migrations_dir / "sqlite"
        )
    elif engine in ("postgresql", "postgres"):
        # Import local : le pilote PostgreSQL n'est chargé que s'il sert.
        from infrastructure.repository.postgres_connector import PostgresConnector

        connector = PostgresConnector(database_url, migrations_dir / "postgres")
    else:
        # Seul le moteur est cité : l'URL complète contient le mot de passe.
        raise ValueError(f"Moteur de base non supporté : {engine}")
    connector.create_schema()
    return connector


@lru_cache
def get_connector() -> DatabaseConnectorInterface:
    return build_connector(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def _mlflow_tracking_uri() -> str:
    return os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_MLFLOW_TRACKING_URI)


def _order_factory() -> OrderFactory:
    return OrderFactory(SqlOrderIdGenerator(get_connector()))


@lru_cache
def get_order_service() -> OrderServiceInterface:
    """Service partagé par toutes les requêtes, construit au premier appel."""
    return OrderService(
        order_repository=SqlOrderRepository(get_connector()),
        order_factory=_order_factory(),
    )


@lru_cache
def get_predict_service() -> "PredictEligibilityInterface":
    """Le modèle champion est chargé à la première prédiction, puis gardé."""
    from application.services.predict_service import PredictService
    from infrastructure.config.training_config import get_training_config
    from infrastructure.ml.predict.mlflow_eligibility_predictor import (
        MlflowEligibilityPredictor,
    )

    config = get_training_config()
    return PredictService(
        order_repository=SqlOrderRepository(get_connector()),
        order_factory=_order_factory(),
        predictor=MlflowEligibilityPredictor(
            tracking_uri=_mlflow_tracking_uri(),
            champion_alias=config.promotion.alias,
            feature_columns=config.features.feature_columns,
            threshold=config.decision.threshold,
        ),
    )


def get_train_service() -> "TrainModelInterface":
    """Utilisé par la CLI d'entraînement uniquement."""
    from application.services.train_service import TrainService
    from infrastructure.config.training_config import get_training_config
    from infrastructure.ml.sklearn_model_trainer import SklearnModelTrainer
    from infrastructure.repository.mlflow_model_repository import (
        MlflowModelRepository,
    )

    config = get_training_config()
    return TrainService(
        orders=SqlOrderRepository(get_connector()),
        trainer=SklearnModelTrainer(config),
        models=MlflowModelRepository(_mlflow_tracking_uri(), config.promotion.alias),
        champion_metrics=config.promotion.metrics,
    )


@lru_cache
def get_training_launcher() -> "TrainingLauncherInterface":
    """Utilisé par l'API d'entraînement : lance la CLI dans un autre processus."""
    from infrastructure.ml.subprocess_training_launcher import (
        SubprocessTrainingLauncher,
    )

    return SubprocessTrainingLauncher()
