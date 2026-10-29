"""Entraînement : le trainer, le service d'entraînement et l'assemblage complet."""

import json

import pytest

from app.core.core import build_prediction_service, build_training_service
from app.core.learning.ml_pipeline import MLPipeline
from app.core.learning.ml_trainer import MLTrainer
from app.core.learning.order_feature import FEATURE_COLUMNS, orders_to_dataframe
from app.core.learning.train_test_splitter import TrainTestSplitter
from app.core.training import TrainingService
from app.infrastructure.implementation.dev.file_model_repository import FileModelRepository
from app.infrastructure.implementation.dev.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from app.infrastructure.implementation.dev.order_generator import generate_labeled_orders


@pytest.fixture
def small_dataset():
    return generate_labeled_orders(n_rows=600, random_state=42)


@pytest.fixture
def trainer(fake_tracker):
    return MLTrainer(
        MLPipeline(random_seed=42).get_model_pipeline(),
        TrainTestSplitter(random_seed=42),
        fake_tracker,
    )


def test_trainer_produces_valid_metrics(trainer, small_dataset):
    run_id, metrics = trainer.train(*small_dataset)

    assert run_id == "run-1"
    assert set(metrics) == {"accuracy", "precision", "recall", "f1_score", "roc_auc"}
    assert all(0.0 <= value <= 1.0 for value in metrics.values())
    # Le générateur a un vrai signal : un modèle qui n'apprend rien serait autour de 0,5.
    assert metrics["roc_auc"] > 0.7


def test_trainer_reports_the_run_to_the_tracker(trainer, fake_tracker, small_dataset):
    _, metrics = trainer.train(*small_dataset)

    [run] = fake_tracker.runs
    assert run["run_name"] == "LogisticRegression"
    assert run["params"] == {
        "model_type": "LogisticRegression",
        "random_state": 42,
        "feature_count": len(FEATURE_COLUMNS),
    }
    assert run["metrics"] == metrics


def test_training_service_saves_model_and_card(trainer, small_dataset, tmp_path, order):
    model_path = tmp_path / "model.joblib"
    service = TrainingService(
        order_repository=InMemoryOrderRepository(*small_dataset),
        trainer=trainer,
        model_repository=FileModelRepository(str(model_path)),
        model_version="9.9.9",
        threshold=0.5,
    )

    result = service.run()

    assert result.run_id == "run-1"
    assert json.loads((tmp_path / "features.json").read_text()) == FEATURE_COLUMNS
    assert json.loads((tmp_path / "metrics.json").read_text()) == pytest.approx(result.metrics)
    reloaded = FileModelRepository(str(model_path)).load()
    probability = reloaded.predict_proba(orders_to_dataframe([order]))[0, 1]
    assert 0.0 <= probability <= 1.0


def test_loading_a_missing_model_returns_none(tmp_path):
    assert FileModelRepository(str(tmp_path / "absent.joblib")).load() is None


def test_in_memory_repository_returns_orders_with_their_labels(small_dataset):
    orders, labels = small_dataset

    assert InMemoryOrderRepository(orders, labels).get_training_data() == (orders, labels)


def test_in_memory_repository_rejects_orders_without_id(order):
    order_without_id = type(order)(**{**order.__dict__, "order_id": None})

    with pytest.raises(ValueError, match="order_id"):
        InMemoryOrderRepository([order_without_id], [1])


def test_full_assembly_trains_then_serves(settings, order):
    """De bout en bout : vraies implémentations, MLflow compris, puis prédiction."""
    assert build_prediction_service(settings) is None

    result = build_training_service(settings).run()
    predict_service = build_prediction_service(settings)

    assert result.run_id
    assert predict_service.predict(order).decision in {"oui", "non"}
