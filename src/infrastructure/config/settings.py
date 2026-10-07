"""Lecture de la configuration : le seul endroit qui lit les variables
d'environnement (alimentées par .env.dev ou .env.prod, voir .env.example)."""

import os
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_DATABASE_URL = "sqlite:///data/commandes.db"


@dataclass(frozen=True)
class Settings:
    # Stockage des commandes (ADR-0001) :
    # - dev       : sqlite:///data/commandes.db
    # - CI / prod : postgresql://commandes_user:<mot de passe>@db:5432/commandes
    database_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
