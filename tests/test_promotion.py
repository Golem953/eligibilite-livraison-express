"""Réentraînement : le nouveau modèle ne remplace le modèle en service que s'il est meilleur."""

import pytest
from fakes.fake_model import FakeModel
from fakes.fake_model_repository import FakeModelRepository

from app.core.learning.chronological_train_test_splitter import ChronologicalTrainTestSplitter
from app.core.learning.ml_pipeline import MLPipeline
from app.core.learning.ml_trainer import MLTrainer
from app.core.promotion_policy import PromotionPolicy
from app.core.training_service import TrainingService
from app.infrastructure.implementation.dev.order_generator import generate_labeled_orders
from app.infrastructure.repository.in_memory_order_repository import (
    InMemoryOrderRepository,
)


@pytest.fixture
def dataset():
    return generate_labeled_orders(n_rows=600, random_state=42)


@pytest.fixture
def trainer(fake_tracker):
    return MLTrainer(
        MLPipeline(random_seed=42).get_model_pipeline(),
        ChronologicalTrainTestSplitter(random_seed=42),
        fake_tracker,
    )


def service(trainer, dataset, model_repository, policy=None):
    return TrainingService(
        order_repository=InMemoryOrderRepository(*dataset),
        trainer=trainer,
        model_repository=model_repository,
        model_version="2.0.0",
        threshold=0.5,
        promotion_policy=policy,
    )


# --- Règle de promotion ---


@pytest.mark.parametrize(
    ("challenger", "champion", "min_gain", "expected"),
    [
        (0.70, None, 0.0, True),
        (0.71, 0.70, 0.0, True),
        (0.70, 0.70, 0.0, False),
        (0.69, 0.70, 0.0, False),
        (0.71, 0.70, 0.02, False),
    ],
)
def test_promotion_policy(challenger, champion, min_gain, expected):
    policy = PromotionPolicy(metric="f1_score", min_gain=min_gain)
    champion_metrics = None if champion is None else {"f1_score": champion}

    assert policy.should_promote({"f1_score": challenger}, champion_metrics) is expected


# --- Découpage chronologique ---


def test_chronological_split_tests_on_the_most_recent_orders(dataset):
    orders, labels = dataset

    X_train, X_test, y_train, y_test = ChronologicalTrainTestSplitter(42).split(orders, labels)

    assert len(X_train) == 480 and len(X_test) == 120
    assert y_train == labels[:480] and y_test == labels[480:]
    assert list(X_test["hour"]) == [order.hour for order in orders[480:]]


# --- Service de réentraînement ---


def test_first_model_is_always_promoted(trainer, dataset):
    model_repository = FakeModelRepository()

    result = service(trainer, dataset, model_repository).run()

    assert result.promoted is True
    assert result.champion_metrics is None
    assert model_repository.saves == 1


def test_better_model_replaces_the_champion(trainer, dataset):
    # Le champion prédit toujours « non » : n'importe quel modèle entraîné fait mieux.
    model_repository = FakeModelRepository(FakeModel(0.1))

    result = service(trainer, dataset, model_repository).run()

    assert result.promoted is True
    assert result.metrics["f1_score"] > result.champion_metrics["f1_score"]
    assert model_repository.model is trainer.model_pipeline


def test_champion_is_kept_when_the_new_model_is_not_better(trainer, dataset, fake_tracker):
    # Même données, même graine : le nouveau modèle est identique au champion, donc pas meilleur.
    first = MLTrainer(
        MLPipeline(random_seed=42).get_model_pipeline(),
        ChronologicalTrainTestSplitter(random_seed=42),
        fake_tracker,
    )
    model_repository = FakeModelRepository()
    service(first, dataset, model_repository).run()
    champion = model_repository.model

    result = service(trainer, dataset, model_repository).run()

    assert result.promoted is False
    assert result.metrics == pytest.approx(result.champion_metrics)
    assert model_repository.saves == 1
    assert model_repository.model is champion


def test_champion_metrics_are_logged_to_the_tracker(trainer, dataset, fake_tracker):
    service(trainer, dataset, FakeModelRepository(FakeModel(0.1))).run()

    [run] = fake_tracker.runs
    assert "champion_f1_score" in run["metrics"]


def test_training_without_labeled_orders_fails_clearly(trainer):
    with pytest.raises(ValueError, match="Aucune commande labellisée"):
        service(trainer, ([], []), FakeModelRepository()).run()
