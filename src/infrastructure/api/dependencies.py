"""Objets partagés par les routes, créés une seule fois.

Les tests les remplacent avec app.dependency_overrides.
"""

from functools import lru_cache

from config.environment import load_environment
from infrastructure.api.model_provider import ModelProvider
from infrastructure.database.database import Database
from infrastructure.database.order_repository import OrderRepository
from infrastructure.ml.model_registry import ModelRegistry


@lru_cache
def get_environment():
    return load_environment()


@lru_cache
def get_database():
    return Database(get_environment().database_url)


@lru_cache
def get_repository():
    return OrderRepository(get_database())


@lru_cache
def get_model_provider():
    return ModelProvider(ModelRegistry(get_environment().mlflow_tracking_uri))
