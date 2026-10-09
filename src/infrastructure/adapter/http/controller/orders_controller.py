# orders_controller.py : la forme idiomatique FastAPI
from fastapi import APIRouter


router = APIRouter(prefix="/v1/orders", tags=["orders"])


@router.post("/")
def create_order(
    order_id: str,
    customer_id: str,
    order_date: str,
    delivery_date: str,
    use_case: GetOrderInterface = Depends(get_get_order),   # ← remplace le __init__
) -> OrderResponse:
    ...


@router.get("/{order_id}")
def get_order(
    order_id: str,
    use_case: GetOrderInterface = Depends(get_get_order),   # ← remplace le __init__
) -> OrderResponse:
    ...
