from fastapi import FastAPI

from infrastructure.adapter.http.controller.predict_controller import (
    router as predict_router,
)

app = FastAPI(title="Éligibilité à la livraison express")
app.include_router(predict_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Utilisée par le healthcheck de docker compose."""
    return {"status": "ok"}
