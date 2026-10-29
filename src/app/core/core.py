"""Racine de composition : le seul endroit qui connaît les classes concrètes.

Chaque point d'entrée assemble uniquement ce dont il a besoin, à partir d'une
configuration reçue en paramètre :

- `build_prediction_service` pour l'API et la commande `predict` ;
- `build_training_service` pour la commande `train`.

Les deux sont indépendants (ADR-0003) : l'API n'importe ni MLflow ni le code
d'entraînement. Changer d'implémentation (PostgreSQL, registre MLflow...) se fait
ici, sans toucher au reste du code.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..infrastructure.repository.file_model_repository import FileModelRepository
from .learning.ml_predict import MLPredict

logger = logging.getLogger(__name__)

EXPERIMENT_NAME = "livraison-express"


def configure_logging(settings: Settings) -> None:
    """Applique LOG_LEVEL au démarrage d'un point d'entrée."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_prediction_service(settings: Settings) -> MLPredict | None:
    """Charge le modèle enregistré. Retourne `None` s'il n'y en a pas encore."""
    model = FileModelRepository(settings.model_path).load()
    if model is None:
        logger.warning("Aucun modèle disponible (%s)", settings.model_path)
        return None
    return MLPredict(
        model,
        threshold=settings.model_threshold,
        model_version=settings.model_version,
    )


def build_training_service(settings: Settings):
    """Assemble l'entraînement : données synthétiques, pipeline, MLflow, fichier modèle."""
    # Imports locaux : seul l'entraînement en a besoin, l'API ne les charge jamais.
    from ..infrastructure.implementation.dev.order_generator import generate_labeled_orders
    from ..infrastructure.implementation.mlflow_tracker import MlflowTracker
    from ..infrastructure.repository.in_memory_order_repository import (
        InMemoryOrderRepository,
    )
    from .learning.ml_pipeline import MLPipeline
    from .learning.ml_trainer import MLTrainer
    from .learning.train_test_splitter import TrainTestSplitter
    from .training_service import TrainingService

    orders, labels = generate_labeled_orders(random_state=settings.random_seed)
    trainer = MLTrainer(
        MLPipeline(random_seed=settings.random_seed).get_model_pipeline(),
        TrainTestSplitter(random_seed=settings.random_seed),
        MlflowTracker(EXPERIMENT_NAME),
    )
    return TrainingService(
        order_repository=InMemoryOrderRepository(orders, labels),
        trainer=trainer,
        model_repository=FileModelRepository(settings.model_path),
        model_version=settings.model_version,
        threshold=settings.model_threshold,
    )
