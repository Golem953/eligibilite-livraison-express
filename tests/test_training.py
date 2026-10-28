"""Entraînement de bout en bout, sur un petit jeu de données synthétiques."""

import json

from app.core.learning.ml_pipeline import MLPipeline
from app.core.learning.ml_trainer import MLTrainer
from app.core.learning.order_feature import FEATURE_COLUMNS, orders_to_dataframe
from app.domain.entities import ModelEntity
from app.infrastructure.implementation.dev.in_memory_model_repository import FileModelRepository
from app.infrastructure.implementation.dev.order_generator import generate_labeled_orders


def train_small_model():
    orders, labels = generate_labeled_orders(n_rows=600, random_state=42)
    pipeline = MLPipeline(random_seed=42).get_model_pipeline()
    run_id, metrics, _, _ = MLTrainer(pipeline).train(orders, labels)
    return pipeline, run_id, metrics


def test_training_produces_valid_metrics(isolated_env):
    _, run_id, metrics = train_small_model()

    assert run_id
    assert set(metrics) == {"accuracy", "precision", "recall", "f1_score", "roc_auc"}
    assert all(0.0 <= value <= 1.0 for value in metrics.values())
    # Le générateur a un vrai signal : un modèle qui n'apprend rien serait autour de 0,5.
    assert metrics["roc_auc"] > 0.7


def test_saved_model_can_be_reloaded_and_used(isolated_env, order):
    pipeline, _, metrics = train_small_model()
    model_path = isolated_env / "artifacts" / "model.joblib"
    repository = FileModelRepository(str(model_path))
    model_card = ModelEntity(
        project="livraison-express-lite",
        model_version="test",
        model_type="LogisticRegression",
        task="classification binaire",
        target="express_eligible",
        threshold=0.5,
        features=FEATURE_COLUMNS,
        metrics=metrics,
    )

    repository.save(pipeline, model_card)
    reloaded = FileModelRepository(str(model_path)).load()

    assert json.loads((model_path.parent / "features.json").read_text()) == FEATURE_COLUMNS
    assert set(json.loads((model_path.parent / "metrics.json").read_text())) == set(metrics)
    probability = reloaded.predict_proba(orders_to_dataframe([order]))[0, 1]
    assert 0.0 <= probability <= 1.0


def test_loading_a_missing_model_returns_none(isolated_env):
    assert FileModelRepository(str(isolated_env / "absent.joblib")).load() is None
