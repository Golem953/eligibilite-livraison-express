"""Lecture de la configuration : le seul endroit qui lit les variables
d'environnement (alimentées par .env.dev ou .env.prod, voir .env.example)."""

import os
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_DATABASE_URL = "sqlite:///data/commandes.db"
# Sans serveur MLflow (dev local hors Docker) : fichier SQLite, ADR-0002.
DEFAULT_MLFLOW_TRACKING_URI = "sqlite:///data/mlflow.db"


@dataclass(frozen=True)
class Settings:
    # Stockage des commandes (ADR-0001) :
    # - dev       : sqlite:///data/commandes.db
    # - CI / prod : postgresql://commandes_user:<mot de passe>@db:5432/commandes
    database_url: str
    # Serveur MLflow (ADR-0002) : http://mlflow:5000 dans docker compose.
    mlflow_tracking_uri: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        mlflow_tracking_uri=os.environ.get(
            "MLFLOW_TRACKING_URI", DEFAULT_MLFLOW_TRACKING_URI
        ),
    )
