"""Entraînement global du modèle (repris du notebook) : nettoyage, contrôles
qualité, sélection des variables, séparation entraînement/test, entraînement
et évaluation. Les valeurs choisies par un humain viennent de training.toml."""

from collections.abc import Callable

from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from application.port.outbound.model_trainer_interface import (
    ModelTrainerInterface,
    TrainedModel,
)
from domain.entities.order import Order
from infrastructure.config.training_config import TrainingConfig
from infrastructure.ml.model_pipeline import build_model_pipeline
from infrastructure.ml.predict.eligibility_prediction import predict_with_threshold
from infrastructure.ml.transform.clean_dataset import CleanDataset
from infrastructure.ml.transform.orders_to_dataframe import OrdersToDataframe
from infrastructure.ml.transform.validate_dataset import ValidateDataset

# Scores disponibles pour [evaluation].metrics : (y_true, y_pred, y_proba) -> score.
# Ajouter un score ici le rend utilisable dans training.toml.
METRIC_FUNCTIONS: dict[str, Callable[..., float]] = {
    "accuracy": lambda y_true, y_pred, y_proba: accuracy_score(y_true, y_pred),
    "precision": lambda y_true, y_pred, y_proba: precision_score(
        y_true, y_pred, zero_division=0
    ),
    "recall": lambda y_true, y_pred, y_proba: recall_score(
        y_true, y_pred, zero_division=0
    ),
    "f1_score": lambda y_true, y_pred, y_proba: f1_score(
        y_true, y_pred, zero_division=0
    ),
    "roc_auc": lambda y_true, y_pred, y_proba: roc_auc_score(y_true, y_proba),
    "balanced_accuracy": lambda y_true, y_pred, y_proba: balanced_accuracy_score(
        y_true, y_pred
    ),
    "average_precision": lambda y_true, y_pred, y_proba: average_precision_score(
        y_true, y_proba
    ),
}


class SklearnModelTrainer(ModelTrainerInterface):
    def __init__(self, config: TrainingConfig) -> None:
        unknown = set(config.evaluation.metrics) - set(METRIC_FUNCTIONS)
        if unknown:
            raise ValueError(
                f"evaluation.metrics inconnus : {sorted(unknown)}. "
                f"Disponibles : {sorted(METRIC_FUNCTIONS)}."
            )
        self._config = config

    def train(self, orders: list[Order]) -> TrainedModel:
        config = self._config
        FEATURE_COLUMNS = config.features.feature_columns
        TARGET_COLUMN = config.features.target_column
        RANDOM_STATE = config.split.random_state

        # Nettoyage puis contrôles qualité
        orders_df = OrdersToDataframe(orders).convert()
        orders_clean = CleanDataset(orders_df, config.quality).clean()
        ValidateDataset(orders_clean, config.quality, TARGET_COLUMN).validate()

        # Sélection des variables
        X = orders_clean[FEATURE_COLUMNS]
        y = orders_clean[TARGET_COLUMN]
        if y.nunique() < 2:
            raise ValueError(
                "Il faut des commandes éligibles et non éligibles pour entraîner."
            )

        # Séparation entraînement/test
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=config.split.test_size,
            random_state=RANDOM_STATE,
            stratify=y,
        )

        # Entraînement du modèle
        model_pipeline = build_model_pipeline(config)
        model_pipeline.fit(X_train, y_train)

        # Évaluation, avec le seuil de décision de la configuration
        y_proba = model_pipeline.predict_proba(X_test)[:, 1]
        y_pred = predict_with_threshold(
            model_pipeline, X_test, threshold=config.decision.threshold
        )["express_eligible"]

        metrics = {
            name: METRIC_FUNCTIONS[name](y_test, y_pred, y_proba)
            for name in config.evaluation.metrics
        }

        params = {
            "model_type": "LogisticRegression",
            "random_state": RANDOM_STATE,
            "feature_count": len(FEATURE_COLUMNS),
            "test_size": config.split.test_size,
            "max_iter": config.model.max_iter,
            "class_weight": config.model.class_weight,
            "threshold": config.decision.threshold,
            "training_rows": len(X_train),
            "test_rows": len(X_test),
        }

        return TrainedModel(
            model=model_pipeline,
            metrics={name: float(value) for name, value in metrics.items()},
            params=params,
            input_example=X_train.head(5),
        )
