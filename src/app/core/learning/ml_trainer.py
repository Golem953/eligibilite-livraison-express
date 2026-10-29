import logging
import time
from collections.abc import Sequence

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from ...domain.entities import OrderEntity
from ...domain.ports import ExperimentTracker
from .order_feature import FEATURE_COLUMNS
from .train_test_splitter import TrainTestSplitter

logger = logging.getLogger(__name__)


class MLTrainer:
    """Entraîne le pipeline, l'évalue et enregistre l'entraînement auprès du tracker."""

    def __init__(
        self,
        model_pipeline,
        splitter: TrainTestSplitter,
        tracker: ExperimentTracker,
    ):
        self.model_pipeline = model_pipeline
        self.splitter = splitter
        self.tracker = tracker

    @property
    def model_type(self) -> str:
        """Nom du classifieur, dernière étape du pipeline (ex. `LogisticRegression`)."""
        return type(self.model_pipeline[-1]).__name__

    def train(
        self,
        orders: Sequence[OrderEntity],
        labels: Sequence[int],
    ) -> tuple[str, dict[str, float]]:
        """Entraîne et évalue le modèle, puis retourne l'identifiant du run et les métriques."""
        started_at = time.perf_counter()
        logger.info("Début du fit du modèle (commandes=%d)", len(orders))
        X_train, X_test, y_train, y_test = self.splitter.split(orders, labels)

        self.model_pipeline.fit(X_train, y_train)
        y_pred = self.model_pipeline.predict(X_test)
        y_proba = self.model_pipeline.predict_proba(X_test)[:, 1]
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, y_proba),
        }
        logger.info(
            "Métriques calculées: %s",
            ", ".join(f"{name}={value:.4f}" for name, value in metrics.items()),
        )

        run_id = self.tracker.log_run(
            run_name=self.model_type,
            params={
                "model_type": self.model_type,
                "random_state": self.splitter.random_seed,
                "feature_count": len(FEATURE_COLUMNS),
            },
            metrics=metrics,
            model=self.model_pipeline,
        )
        logger.info(
            "Entraînement ML terminé (run_id=%s, durée=%.2f s)",
            run_id,
            time.perf_counter() - started_at,
        )
        return run_id, metrics
