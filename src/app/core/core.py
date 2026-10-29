"""Racine de composition : le seul endroit qui connaît les classes concrètes.

Chaque point d'entrée assemble uniquement ce dont il a besoin, à partir d'une
configuration reçue en paramètre :

- `build_prediction_service` pour l'API et la commande `predict` ;
- `build_training_service` pour la commande `train`, avec la source des commandes
  choisie par `build_order_repository`.

Les deux sont indépendants (ADR-0003) : l'API n'importe ni MLflow ni le code
d'entraînement. Changer d'implémentation (PostgreSQL, registre MLflow...) se fait
ici, sans toucher au reste du code.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..domain.interface.order_repository_interface import OrderRepositoryInterface
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


def build_order_repository(settings: Settings) -> OrderRepositoryInterface:
    """Choisit la source des commandes selon `TRAINING_SOURCE_URL` (ADR-0009)."""
    url = settings.training_source_url
    if url == "memory://":
        from ..infrastructure.implementation.dev.order_generator import generate_labeled_orders
        from ..infrastructure.repository.in_memory_order_repository import (
            InMemoryOrderRepository,
        )

        repository = InMemoryOrderRepository()
        for order, label in zip(*generate_labeled_orders(random_state=settings.random_seed)):
            repository.save(order, label)
        return repository
    if url.startswith(("mongodb://", "mongodb+srv://")):
        from ..infrastructure.repository.mongo_order_repository import MongoOrderRepository

        return MongoOrderRepository.from_url(url)
    raise ValueError("TRAINING_SOURCE_URL doit commencer par memory:// ou mongodb://")


def build_training_service(settings: Settings):
    """Assemble l'entraînement : source des commandes, pipeline, MLflow, fichier modèle."""
    # Imports locaux : seul l'entraînement en a besoin, l'API ne les charge jamais.
    from ..infrastructure.implementation.mlflow_tracker import MlflowTracker
    from .learning.chronological_train_test_splitter import ChronologicalTrainTestSplitter
    from .learning.ml_pipeline import MLPipeline
    from .learning.ml_trainer import MLTrainer
    from .learning.train_test_splitter import TrainTestSplitter
    from .promotion_policy import PromotionPolicy
    from .training_service import TrainingService

    # Commandes de l'ERP : test sur les plus récentes, pour comparer le nouveau modèle et
    # le modèle en service sur des commandes qu'aucun n'a vues (ADR-0009). En mémoire :
    # découpage aléatoire du notebook.
    splitter_class = (
        TrainTestSplitter
        if settings.training_source_url == "memory://"
        else ChronologicalTrainTestSplitter
    )
    trainer = MLTrainer(
        MLPipeline(random_seed=settings.random_seed).get_model_pipeline(),
        splitter_class(random_seed=settings.random_seed),
        MlflowTracker(EXPERIMENT_NAME),
    )
    return TrainingService(
        order_repository=build_order_repository(settings),
        trainer=trainer,
        model_repository=FileModelRepository(settings.model_path),
        model_version=settings.model_version,
        threshold=settings.model_threshold,
        promotion_policy=PromotionPolicy(
            metric=settings.promotion_metric,
            min_gain=settings.promotion_min_gain,
        ),
    )
