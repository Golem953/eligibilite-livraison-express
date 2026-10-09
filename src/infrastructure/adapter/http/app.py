from fastapi import FastAPI

from infrastructure.adapter.http.controller.orders_controller import (
    router as orders_router,
)

app = FastAPI(title="Éligibilité à la livraison express")
app.include_router(orders_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Utilisée par le healthcheck de docker compose."""
    return {"status": "ok"}
