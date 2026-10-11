from fastapi import APIRouter, BackgroundTasks, Depends

from infrastructure.api.dependencies import get_model_provider, get_repository
from infrastructure.api.errors import (
    ApiError,
    error_responses,
    order_rejected_error,
)
from infrastructure.api.prediction import predict_in_background
from infrastructure.api.schemas import OrderAccepted, OrderFeatures
from infrastructure.database.order_repository import OrderRejectedError

router = APIRouter(prefix="/v1/orders", tags=["orders"])


@router.post(
    "",
    status_code=202,
    response_model=OrderAccepted,
    operation_id="createOrder",
    summary="Enregistrer une commande à prédire",
    responses=error_responses(422, 500),
)
def create_order(
    order: OrderFeatures,
    background_tasks: BackgroundTasks,
    repository=Depends(get_repository),
    model_provider=Depends(get_model_provider),
):
    """La commande est enregistrée, la réponse est immédiate et la prédiction est
    calculée après la réponse (relisible avec GET /v1/predictions/{order_id})."""
    features = order.model_dump(exclude={"order_id"})
    try:
        order_id = repository.add_order(features, order_id=order.order_id)
    except OrderRejectedError as error:
        raise order_rejected_error() from error

    background_tasks.add_task(
        predict_in_background, order_id, features, model_provider, repository
    )
    return OrderAccepted(order_id=order_id)


@router.get(
    "/{order_id}",
    response_model=OrderFeatures,
    response_model_exclude_none=True,
    operation_id="getOrder",
    summary="Relire une commande collectée",
    responses=error_responses(404),
)
def get_order(order_id: str, repository=Depends(get_repository)):
    order = repository.get_order(order_id)
    if order is None:
        raise ApiError(404, "order_not_found", f"Commande inconnue : {order_id}")
    return order
