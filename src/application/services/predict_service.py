from dataclasses import replace

from application.port.inbound.predict_eligibility_interface import (
    PredictEligibilityInterface,
)
from application.port.outbound.eligibility_predictor_interface import (
    EligibilityPredictorInterface,
)
from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from domain.entities.order import Order, OrderStatus, Prediction


class PredictService(PredictEligibilityInterface):
    """Prédit avec le modèle champion, puis enregistre la commande avec sa
    prédiction (ADR-0001). Prédire avant d'enregistrer évite de stocker des
    commandes « reçues » orphelines quand aucun modèle n'est disponible."""

    def __init__(
        self,
        orders: OrderRepositoryInterface,
        predictor: EligibilityPredictorInterface,
    ) -> None:
        self._orders = orders
        self._predictor = predictor

    def predict(self, order: Order) -> Prediction:
        prediction = self._predictor.predict(order)
        self._orders.save(_with_prediction(order, prediction))
        return prediction

    def predict_batch(self, orders: list[Order]) -> list[Prediction]:
        predictions = self._predictor.predict_batch(orders)
        self._orders.save_all(
            [
                _with_prediction(order, prediction)
                for order, prediction in zip(orders, predictions, strict=True)
            ]
        )
        return predictions


def _with_prediction(order: Order, prediction: Prediction) -> Order:
    return replace(order, status=OrderStatus.PREDICTED, prediction=prediction)
