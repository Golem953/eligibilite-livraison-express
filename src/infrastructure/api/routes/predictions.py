from fastapi import APIRouter, Depends

from infrastructure.api.dependencies import get_model_provider, get_repository
from infrastructure.api.errors import (
    ApiError,
    error_responses,
    order_rejected_error,
)
from infrastructure.api.prediction import predict_many, predict_one, require_model
from infrastructure.api.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    OrderFeatures,
    Prediction,
)
from infrastructure.database.order_repository import OrderRejectedError

router = APIRouter(prefix="/v1/predictions", tags=["predictions"])


@router.post(
    "",
    response_model=Prediction,
    operation_id="createPrediction",
    summary="Prédire l'éligibilité express d'une commande",
    responses=error_responses(422, 503),
)
def create_prediction(
    order: OrderFeatures,
    repository=Depends(get_repository),
    model_provider=Depends(get_model_provider),
):
    """Prédiction synchrone (cellule 34 du notebook). La commande et sa prédiction
    sont enregistrées."""
    loaded_model = require_model(model_provider)
    features = order.model_dump(exclude={"order_id"})
    try:
        order_id = repository.add_order(features, order_id=order.order_id)
    except OrderRejectedError as error:
        raise order_rejected_error() from error

    prediction = predict_one(order_id, features, loaded_model)
    repository.save_predictions([prediction])
    return prediction


@router.post(
    "/batch",
    response_model=BatchPredictionResponse,
    operation_id="createBatchPredictions",
    summary="Prédire un lot de commandes",
    responses=error_responses(422, 503),
)
def create_batch_predictions(
    batch: BatchPredictionRequest,
    repository=Depends(get_repository),
    model_provider=Depends(get_model_provider),
):
    """Prédiction batch (cellule 46 du notebook), dans l'ordre des commandes reçues."""
    loaded_model = require_model(model_provider)
    orders = [order.model_dump() for order in batch.orders]
    try:
        order_ids = repository.add_orders(orders)
    except OrderRejectedError as error:
        raise order_rejected_error() from error

    batch_predictions = predict_many(order_ids, orders, loaded_model)
    repository.save_predictions(batch_predictions)
    return BatchPredictionResponse(
        predictions=batch_predictions, count=len(batch_predictions)
    )


@router.get(
    "/{order_id}",
    response_model=Prediction,
    operation_id="getPrediction",
    summary="Relire une prédiction déjà calculée",
    responses=error_responses(404),
)
def get_prediction(order_id: str, repository=Depends(get_repository)):
    prediction = repository.get_prediction(order_id)
    if prediction is None:
        raise ApiError(404, "prediction_not_found", f"Prédiction inconnue : {order_id}")
    return prediction
