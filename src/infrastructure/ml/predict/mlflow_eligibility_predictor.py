import threading
from datetime import UTC, datetime
from typing import Any

import mlflow.sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from application.port.outbound.eligibility_predictor_interface import (
    EligibilityPredictorInterface,
)
from domain.entities.order import Order, Prediction
from infrastructure.ml.predict.eligibility_prediction import (
    batch_predict_orders,
    predict_order_eligibility,
)
from infrastructure.ml.transform.orders_to_dataframe import OrdersToDataframe
from infrastructure.repository.mlflow_model_repository import REGISTERED_MODEL_NAME


class MlflowEligibilityPredictor(EligibilityPredictorInterface):
    """Prédit avec la version champion du registre MLflow (ADR-0002).

    Le modèle est chargé une seule fois, à la première prédiction, puis gardé en
    mémoire : un nouveau champion n'est pris en compte qu'au redémarrage.
    """

    def __init__(
        self,
        tracking_uri: str,
        champion_alias: str,
        feature_columns: list[str],
        threshold: float,
    ) -> None:
        self._client = MlflowClient(tracking_uri)
        self._tracking_uri = tracking_uri
        self._champion_alias = champion_alias
        self._feature_columns = feature_columns
        self._threshold = threshold
        self._model: Any = None
        self._model_version: str | None = None
        self._lock = threading.Lock()

    def predict(self, order: Order) -> Prediction:
        model, version = self._champion()
        order_data = OrdersToDataframe([order]).convert().to_dict("records")[0]
        result = predict_order_eligibility(
            order_data, model, self._feature_columns, version, self._threshold
        )
        return Prediction(
            eligible=result["express_eligible"],
            probability=result["probability"],
            model_version=result["model_version"],
            predicted_at=datetime.fromisoformat(result["prediction_timestamp"]),
        )

    def predict_batch(self, orders: list[Order]) -> list[Prediction]:
        model, version = self._champion()
        result = batch_predict_orders(
            OrdersToDataframe(orders).convert(),
            model,
            self._feature_columns,
            self._threshold,
        )
        predicted_at = datetime.now(UTC)
        return [
            Prediction(
                eligible=bool(row.express_eligible),
                probability=round(float(row.eligibility_probability), 4),
                model_version=version,
                predicted_at=predicted_at,
            )
            for row in result.itertuples(index=False)
        ]

    def _champion(self) -> tuple[Any, str]:
        with self._lock:
            if self._model is None:
                try:
                    champion = self._client.get_model_version_by_alias(
                        REGISTERED_MODEL_NAME, self._champion_alias
                    )
                except MlflowException as error:
                    raise LookupError(
                        "Aucun modèle champion : lancer un entraînement (POST /train)."
                    ) from error
                mlflow.set_tracking_uri(self._tracking_uri)
                self._model = mlflow.sklearn.load_model(
                    f"models:/{REGISTERED_MODEL_NAME}/{champion.version}"
                )
                self._model_version = str(champion.version)
            return self._model, self._model_version
