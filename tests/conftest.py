from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from domain.ml_feature import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from infrastructure.api.app import app
from infrastructure.api.dependencies import (
    get_database,
    get_model_provider,
    get_repository,
)
from infrastructure.database.database import Database
from infrastructure.database.order_repository import OrderRepository
from infrastructure.generation.order_generator import OrderGenerator
from infrastructure.ml.data_splitter import DataSplitter
from infrastructure.ml.ml_pipeline import MLPipeline
from infrastructure.ml.model_registry import LoadedModel
from infrastructure.nettoyage.clean import Clean

VALID_ORDER = {
    "hour": 10,
    "day_of_week": 1,
    "weekend": 0,
    "distance_km": 2,
    "order_value_eur": 50,
    "weight_kg": 1,
    "stock_available": 1,
    "preparation_time_min": 10,
    "carrier_capacity": 0.9,
    "weather": "normal",
    "delivery_zone": "centre",
    "customer_type": "premium",
}


@pytest.fixture(scope="session")
def trained_model():
    """Pipeline du notebook entraînée sur des commandes générées (sans MLflow)."""
    orders = Clean.clean_orders_data(
        OrderGenerator.generate_orders_dataset(n_rows=1500)
    )
    X, y = DataSplitter(orders).split_data(None, None)
    model = MLPipeline(NUMERIC_FEATURES, CATEGORICAL_FEATURES).build_model()
    return model.fit(X, y)


class FakeModelProvider:
    def __init__(self, loaded_model):
        self.loaded_model = loaded_model

    def get(self):
        return self.loaded_model


@pytest.fixture
def database(tmp_path):
    return Database(f"sqlite:///{tmp_path / 'test.db'}")


def _client(database, loaded_model):
    repository = OrderRepository(database)
    provider = FakeModelProvider(loaded_model)
    app.dependency_overrides = {
        get_database: lambda: database,
        get_repository: lambda: repository,
        get_model_provider: lambda: provider,
    }
    return TestClient(app)


@pytest.fixture
def client(database, trained_model):
    loaded_model = LoadedModel(
        model=trained_model,
        version="3",
        run_id="test-run",
        metrics={"accuracy": 0.86, "f1_score": 0.86},
        trained_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with _client(database, loaded_model) as test_client:
        yield test_client
    app.dependency_overrides = {}


@pytest.fixture
def client_without_model(database):
    with _client(database, None) as test_client:
        yield test_client
    app.dependency_overrides = {}
