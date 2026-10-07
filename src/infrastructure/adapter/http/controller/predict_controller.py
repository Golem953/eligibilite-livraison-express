from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from application.port.inbound.predict_eligibility_interface import (
    PredictEligibilityInterface,
)
from domain.entities.order import Order, Prediction
from infrastructure.adapter.dependency_injection.container import (
    get_predict_service,
)

router = APIRouter()


class OrderRequest(BaseModel):
    """Commande à évaluer. Sans order_id, un identifiant est généré ; sans
    order_date, la date de réception est utilisée."""

    order_id: str | None = None
    order_date: datetime | None = None
    hour: int
    day_of_week: int
    weekend: bool
    distance_km: float
    order_value_eur: float
    weight_kg: float
    stock_available: bool
    preparation_time_min: float
    carrier_capacity: float
    weather: str
    delivery_zone: str
    customer_type: str


class PredictionResponse(BaseModel):
    order_id: str
    express_eligible: bool
    decision: str
    probability: float
    model_version: str
    prediction_timestamp: datetime


PredictService = Annotated[PredictEligibilityInterface, Depends(get_predict_service)]


@router.post("/predict")
def predict(request: OrderRequest, service: PredictService) -> PredictionResponse:
    order = _to_order(request)
    prediction = _call(lambda: service.predict(order))
    return _to_response(order, prediction)


@router.post("/predict/batch")
def predict_batch(
    requests: list[OrderRequest], service: PredictService
) -> list[PredictionResponse]:
    orders = [_to_order(request) for request in requests]
    predictions = _call(lambda: service.predict_batch(orders))
    return [
        _to_response(order, prediction)
        for order, prediction in zip(orders, predictions, strict=True)
    ]


def _to_order(request: OrderRequest) -> Order:
    order_date = request.order_date or datetime.now(UTC)
    if order_date.tzinfo is None:
        order_date = order_date.replace(tzinfo=UTC)
    try:
        return Order(
            **request.model_dump(exclude={"order_id", "order_date"}),
            order_id=request.order_id or str(uuid4()),
            order_date=order_date,
        )
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)
        ) from error


def _call(use_case):
    try:
        return use_case()
    except LookupError as error:  # pas de modèle champion
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except ValueError as error:  # identifiant déjà utilisé, données refusées
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


def _to_response(order: Order, prediction: Prediction) -> PredictionResponse:
    return PredictionResponse(
        order_id=order.order_id,
        express_eligible=prediction.eligible,
        decision="oui" if prediction.eligible else "non",
        probability=prediction.probability,
        model_version=prediction.model_version,
        prediction_timestamp=prediction.predicted_at,
    )
