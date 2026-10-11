"""Point d'entrée de l'API : uvicorn infrastructure.api.app:app"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.settings import APP_VERSION, PROJECT_NAME
from infrastructure.api.dependencies import get_database, get_model_provider
from infrastructure.api.errors import register_error_handlers
from infrastructure.api.routes import health, model, orders, predictions

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Les tests remplacent ces objets avec app.dependency_overrides.
    overrides = app.dependency_overrides
    overrides.get(get_database, get_database)().create_tables()
    # Premier chargement du modèle au démarrage (non bloquant s'il est absent).
    overrides.get(get_model_provider, get_model_provider)().get()
    yield


app = FastAPI(
    title=f"{PROJECT_NAME} API",
    version=APP_VERSION,
    description="API de prédiction d'éligibilité à la livraison express.",
    lifespan=lifespan,
)
register_error_handlers(app)
app.include_router(health.router)
app.include_router(orders.router)
app.include_router(predictions.router)
app.include_router(model.router)
