from dataclasses import replace
from typing import Any

from application.port.inbound.predict_eligibility_interface import (
    PredictEligibilityInterface,
)
from application.port.outbound.eligibility_predictor_interface import (
    EligibilityPredictorInterface,
)
from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from domain.custom_execption.order_already_exists_error import (
    OrderAlreadyExistsError,
)
from domain.entities.order import Order
from domain.factory.order_factory import OrderFactory
from domain.value_objects.order_status import OrderStatus


class PredictService(PredictEligibilityInterface):
    """Prédit avec le modèle champion, puis enregistre la commande avec sa
    prédiction (ADR-0001). Prédire avant d'enregistrer évite de stocker des
    commandes « reçues » orphelines quand aucun modèle n'est disponible."""

    def __init__(
        self,
        order_repository: OrderRepositoryInterface,
        order_factory: OrderFactory,
        predictor: EligibilityPredictorInterface,
    ) -> None:
        self._order_repository = order_repository
        self._order_factory = order_factory
        self._predictor = predictor

    def predict(self, order_id: str | None = None, **features: Any) -> Order:
        if order_id is not None and self._order_repository.get_order_by_id(order_id):
            raise OrderAlreadyExistsError(order_id)
        order = self._order_factory.create(order_id=order_id, **features)
        prediction = self._predictor.predict(order)
        predicted = replace(order, status=OrderStatus.PREDICTED, prediction=prediction)
        self._order_repository.save(predicted)
        return predicted
