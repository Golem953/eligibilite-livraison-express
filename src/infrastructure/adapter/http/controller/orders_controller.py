from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from application.port.inbound.order_service_interface import OrderServiceInterface
from domain.custom_execption.order_already_exists_error import (
    OrderAlreadyExistsError,
)
from domain.entities.order import Order
from infrastructure.adapter.dependency_injection.container import get_order_service

router = APIRouter(prefix="/v1/orders", tags=["orders"])

OrderService = Annotated[OrderServiceInterface, Depends(get_order_service)]


class ErrorResponse(BaseModel):
    """Schéma Error du contrat OpenAPI."""

    error: str
    message: str
    details: list[str] | None = None


class OrderFeatures(BaseModel):
    """Schéma OrderFeatures du contrat : toute variable en trop donne une 422."""

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = Field(default=None, min_length=1, max_length=50)
    hour: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    weekend: Literal[0, 1]
    distance_km: float = Field(ge=0)
    order_value_eur: float = Field(ge=0)
    weight_kg: float = Field(ge=0)
    stock_available: Literal[0, 1]
    preparation_time_min: float = Field(ge=0)
    carrier_capacity: float = Field(ge=0, le=1)
    weather: Literal["normal", "pluie", "neige", "orage"]
    delivery_zone: Literal["centre", "proche_banlieue", "banlieue", "rurale"]
    customer_type: Literal["standard", "premium"]

    @classmethod
    def from_order(cls, order: Order) -> "OrderFeatures":
        """Domaine → HTTP : les booléens repassent en 0/1 comme dans le contrat."""
        return cls(
            order_id=order.order_id,
            hour=order.hour,
            day_of_week=order.day_of_week,
            weekend=int(order.weekend),
            distance_km=order.distance_km,
            order_value_eur=order.order_value_eur,
            weight_kg=order.weight_kg,
            stock_available=int(order.stock_available),
            preparation_time_min=order.preparation_time_min,
            carrier_capacity=order.carrier_capacity,
            weather=order.weather,
            delivery_zone=order.delivery_zone,
            customer_type=order.customer_type,
        )


class OrderAccepted(BaseModel):
    order_id: str
    status: Literal["accepted"] = "accepted"


@router.post(
    "",
    status_code=202,
    operation_id="createOrder",
    summary="Enregistrer une commande à prédire",
    responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def create_order(body: OrderFeatures, service: OrderService) -> OrderAccepted:
    features = body.model_dump(exclude={"order_id"})
    # HTTP → domaine : 0/1 du contrat → booléens.
    features["weekend"] = bool(features["weekend"])
    features["stock_available"] = bool(features["stock_available"])
    try:
        order = service.create_order(order_id=body.order_id, **features)
    except OrderAlreadyExistsError as error:
        raise HTTPException(
            status_code=422,
            detail={"error": "order_already_exists", "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_order", "message": str(error)},
        ) from error
    return OrderAccepted(order_id=order.order_id)


@router.get(
    "/{order_id}",
    operation_id="getOrder",
    summary="Relire une commande collectée",
    responses={404: {"model": ErrorResponse}},
)
def get_order(order_id: str, service: OrderService) -> OrderFeatures:
    order = service.get_order(order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "order_not_found",
                "message": f"La commande {order_id} n'existe pas.",
            },
        )
    return OrderFeatures.from_order(order)
