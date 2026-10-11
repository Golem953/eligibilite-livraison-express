"""Erreurs de l'API au format Error du contrat : {error, message, details}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from infrastructure.api.schemas import Error

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status_code, error, message, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.details = details


def order_rejected_error():
    return ApiError(
        422, "order_rejected", "Commande refusée (identifiant déjà utilisé ?)"
    )


def error_responses(*status_codes):
    """Documente les réponses d'erreur d'une route dans /docs."""
    return {code: {"model": Error} for code in status_codes}


def _error_response(status_code, error, message, details=None):
    body = Error(error=error, message=message, details=details)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_error_handlers(app: FastAPI):
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError):
        return _error_response(exc.status_code, exc.error, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError):
        details = [
            f"{'.'.join(str(part) for part in error['loc'][1:])} : {error['msg']}"
            for error in exc.errors()
        ]
        return _error_response(422, "validation_error", details[0], details)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception):
        logger.exception("Erreur interne", exc_info=exc)
        return _error_response(500, "internal_error", "Erreur interne du serveur")
