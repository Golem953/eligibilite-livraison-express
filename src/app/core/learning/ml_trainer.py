import logging
import time
from collections.abc import Sequence

import mlflow
import mlflow.sklearn
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from ...config import Settings
from ...domain.entities import OrderEntity
from .ml_pipeline import MLPipeline
from .order_feature import FEATURE_COLUMNS
from .train_test_splitter import TrainTestSplitter

logger = logging.getLogger(__name__)

class MLTrainer:
    def __init__(self, model_pipeline=None):
        mlflow.set_experiment("livraison-express")
        self.model_pipeline = model_pipeline or MLPipeline().get_model_pipeline()
        logger.debug("MLTrainer initialisé (expérience=livraison-express)")

    def train(
        self,
        orders: Sequence[OrderEntity],
        labels: Sequence[int],
        data_splitter: TrainTestSplitter | None = None,
    ):
        started_at = time.perf_counter()
        splitter = data_splitter or TrainTestSplitter()
        logger.info("Début du fit du modèle (commandes=%d)", len(orders))
        X_train, X_test, y_train, y_test = splitter.split(orders, labels)

        with mlflow.start_run(run_name="logistic-regression-baseline") as run:
            logger.info("Run MLflow démarré (run_id=%s)", run.info.run_id)
            self.model_pipeline.fit(X_train, y_train)
            logger.info("Pipeline entraîné")

            y_pred = self.model_pipeline.predict(X_test)
            y_proba = self.model_pipeline.predict_proba(X_test)[:, 1]

            metrics = {
                "accuracy": accuracy_score(y_test, y_pred),
                "precision": precision_score(y_test, y_pred, zero_division=0),
                "recall": recall_score(y_test, y_pred, zero_division=0),
                "f1_score": f1_score(y_test, y_pred, zero_division=0),
                "roc_auc": roc_auc_score(y_test, y_proba),
            }

            mlflow.log_param("model_type", "LogisticRegression")
            mlflow.log_param("random_state", Settings().random_seed)
            mlflow.log_param("feature_count", len(FEATURE_COLUMNS))

            for metric_name, metric_value in metrics.items():
                mlflow.log_metric(metric_name, metric_value)

            logger.info(
                "Métriques calculées: %s",
                ", ".join(f"{name}={value:.4f}" for name, value in metrics.items()),
            )

            mlflow.sklearn.log_model(
                self.model_pipeline,
                name="model",
                skops_trusted_types=["numpy.dtype"],
            )
            logger.info("Modèle enregistré dans MLflow (name=model)")

            run_id = run.info.run_id

            logger.info(
                "Entraînement ML terminé (run_id=%s, durée=%.2f s)",
                run_id,
                time.perf_counter() - started_at,
            )
            return run_id, metrics, y_pred, y_proba
        return None
