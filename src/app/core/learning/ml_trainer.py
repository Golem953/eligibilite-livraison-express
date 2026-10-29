import logging
import time
from collections.abc import Sequence

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from ...domain.entities.order_entity import OrderEntity
from ...domain.interface.experiment_tracker_interface import ExperimentTrackerInterface
from .order_feature import FEATURE_COLUMNS
from .train_test_splitter import TrainTestSplitter

logger = logging.getLogger(__name__)


class MLTrainer:
    """Entraîne le pipeline, l'évalue et enregistre l'entraînement auprès du tracker."""

    def __init__(
        self,
        model_pipeline,
        splitter: TrainTestSplitter,
        tracker: ExperimentTrackerInterface,
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
        champion: object | None = None,
    ) -> tuple[str, dict[str, float], dict[str, float] | None]:
        """Entraîne et évalue le modèle, ainsi que `champion` (le modèle en service) s'il y
        en a un, sur le même jeu de test.

        Retourne l'identifiant du run, les métriques du nouveau modèle et celles du
        champion (`None` sans champion).
        """
        started_at = time.perf_counter()
        logger.info("Début du fit du modèle (commandes=%d)", len(orders))
        X_train, X_test, y_train, y_test = self.splitter.split(orders, labels)

        self.model_pipeline.fit(X_train, y_train)
        metrics = self._evaluate(self.model_pipeline, X_test, y_test)
        logger.info("Métriques calculées: %s", _format(metrics))

        champion_metrics = None
        if champion is not None:
            champion_metrics = self._evaluate(champion, X_test, y_test)
            logger.info("Métriques du modèle en service: %s", _format(champion_metrics))

        run_id = self.tracker.log_run(
            run_name=self.model_type,
            params={
                "model_type": self.model_type,
                "random_state": self.splitter.random_seed,
                "feature_count": len(FEATURE_COLUMNS),
            },
            metrics={
                **metrics,
                **{f"champion_{name}": value for name, value in (champion_metrics or {}).items()},
            },
            model=self.model_pipeline,
        )
        logger.info(
            "Entraînement ML terminé (run_id=%s, durée=%.2f s)",
            run_id,
            time.perf_counter() - started_at,
        )
        return run_id, metrics, champion_metrics

    @staticmethod
    def _evaluate(model, X_test, y_test) -> dict[str, float]:
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        return {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, y_proba),
        }


def _format(metrics: dict[str, float]) -> str:
    return ", ".join(f"{name}={value:.4f}" for name, value in metrics.items())
