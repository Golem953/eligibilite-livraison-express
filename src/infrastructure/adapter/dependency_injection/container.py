"""Composition root : le seul endroit qui choisit les adapters.

Les valeurs viennent de la configuration (infrastructure/config/settings.py) :
le stockage des commandes est choisi par le préfixe de DATABASE_URL (ADR-0001).

Ajouter un moteur = écrire sa fabrique et l'enregistrer dans _REPOSITORY_FACTORIES :
- moteur SQL (MariaDB, MySQL…) : un connecteur implémentant
  DatabaseConnectorInterface, passé à SqlOrderRepository ;
- moteur non SQL (MongoDB…) : un nouveau OrderRepositoryInterface, sans connecteur SQL.
"""

from collections.abc import Callable
from functools import lru_cache

from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)
from infrastructure.config.settings import get_settings
from infrastructure.repository.sql_order_repository import SqlOrderRepository


def _sqlite_order_repository(url: str) -> OrderRepositoryInterface:
    from infrastructure.repository.sqlite_connector import SqliteConnector

    connector = SqliteConnector(url.removeprefix("sqlite:///"))
    connector.create_schema()
    return SqlOrderRepository(connector)


def _postgres_order_repository(url: str) -> OrderRepositoryInterface:
    # Import local : le pilote PostgreSQL n'est chargé que s'il sert.
    from infrastructure.repository.postgres_connector import PostgresConnector

    connector = PostgresConnector(url)
    connector.create_schema()
    return SqlOrderRepository(connector)


# Préfixe de DATABASE_URL (avant « :// ») → fabrique du repository.
_REPOSITORY_FACTORIES: dict[str, Callable[[str], OrderRepositoryInterface]] = {
    "sqlite": _sqlite_order_repository,
    "postgresql": _postgres_order_repository,
    "postgres": _postgres_order_repository,
}


def build_order_repository(database_url: str) -> OrderRepositoryInterface:
    scheme = database_url.split("://", 1)[0]
    factory = _REPOSITORY_FACTORIES.get(scheme)
    if factory is None:
        raise ValueError(
            f"Moteur de base de données non supporté : « {scheme} ». "
            f"Moteurs disponibles : {sorted(_REPOSITORY_FACTORIES)}."
        )
    return factory(database_url)


@lru_cache
def get_order_repository() -> OrderRepositoryInterface:
    """À injecter dans les routes avec `Depends(get_order_repository)`."""
    return build_order_repository(get_settings().database_url)
