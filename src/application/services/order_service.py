from typing import Any

from application.port.inbound.order_service_interface import OrderServiceInterface
from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from domain.custom_execption.order_already_exists_error import (
    OrderAlreadyExistsError,
)
from domain.entities.order import Order
from domain.factory.order_factory import OrderFactory


class OrderService(OrderServiceInterface):
    def __init__(
        self, order_repository: OrderRepositoryInterface, order_factory: OrderFactory
    ) -> None:
        self._order_repository = order_repository
        self._order_factory = order_factory

    def create_order(self, order_id: str | None = None, **features: Any) -> Order:
        # Contrôle explicite : le message ne dépend pas du moteur de base.
        if order_id is not None and self._order_repository.get_order_by_id(order_id):
            raise OrderAlreadyExistsError(order_id)
        order = self._order_factory.create(order_id=order_id, **features)
        self._order_repository.save(order)
        return order

    def get_order(self, order_id: str) -> Order | None:
        return self._order_repository.get_order_by_id(order_id)
