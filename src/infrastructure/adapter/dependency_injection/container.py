"""Composition root : le seul endroit qui choisit les adapters.

Le moteur de base est choisi par le préfixe de DATABASE_URL (ADR-0001) :
  sqlite:///data/commandes.db
  postgresql://commandes_user:…@db:5432/commandes
"""

import os
from functools import lru_cache
from pathlib import Path

from application.port.inbound.order_service_interface import OrderServiceInterface
from application.services.order_service import OrderService
from domain.factory.order_factory import OrderFactory
from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
)
from infrastructure.repository.sql_order_id_generator import SqlOrderIdGenerator
from infrastructure.repository.sql_order_repository import SqlOrderRepository

DEFAULT_DATABASE_URL = "sqlite:///data/commandes.db"
# Racine du dépôt en dev (src/infrastructure/adapter/dependency_injection/…).
# Dans l'image Docker, MIGRATIONS_DIR est fixé par le Dockerfile.
DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations"


def build_connector(database_url: str) -> DatabaseConnectorInterface:
    """Connecteur du moteur désigné par l'URL, schéma à jour."""
    migrations_dir = Path(os.environ.get("MIGRATIONS_DIR", DEFAULT_MIGRATIONS_DIR))
    engine = database_url.split("://", 1)[0]
    if engine == "sqlite":
        from infrastructure.repository.sqlite_connector import SqliteConnector

        connector: DatabaseConnectorInterface = SqliteConnector(
            database_url.removeprefix("sqlite:///"), migrations_dir / "sqlite"
        )
    elif engine in ("postgresql", "postgres"):
        # Import local : le pilote PostgreSQL n'est chargé que s'il sert.
        from infrastructure.repository.postgres_connector import PostgresConnector

        connector = PostgresConnector(database_url, migrations_dir / "postgres")
    else:
        # Seul le moteur est cité : l'URL complète contient le mot de passe.
        raise ValueError(f"Moteur de base non supporté : {engine}")
    connector.create_schema()
    return connector


def build_order_service(database_url: str) -> OrderServiceInterface:
    connector = build_connector(database_url)
    return OrderService(
        order_repository=SqlOrderRepository(connector),
        order_factory=OrderFactory(SqlOrderIdGenerator(connector)),
    )


@lru_cache
def get_order_service() -> OrderServiceInterface:
    """Service partagé par toutes les requêtes, construit au premier appel."""
    return build_order_service(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
