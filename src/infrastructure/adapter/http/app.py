import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from infrastructure.adapter.http.controller.orders_controller import (
    router as orders_router,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Éligibilité à la livraison express")
app.include_router(orders_router)


# Toutes les erreurs suivent le schéma Error du contrat : {error, message, details}.


@app.exception_handler(RequestValidationError)
async def validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        f"{'.'.join(str(part) for part in error['loc'] if part != 'body')} : "
        f"{error['msg']}"
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Requête invalide.",
            "details": details,
        },
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    # Les controllers passent déjà {error, message} ; sinon (404 de route
    # inconnue, 405…), on l'enveloppe.
    content = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"error": "http_error", "message": str(exc.detail)}
    )
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erreur non gérée")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "Erreur interne."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Utilisée par le healthcheck de docker compose."""
    return {"status": "ok"}
