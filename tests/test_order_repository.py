"""Repositories de commandes : un même contrat pour toutes les implémentations (ADR-0001)."""

import dataclasses

import pytest
from fakes.fake_mongo_collection import FakeMongoCollection

from app.core.core import build_order_repository
from app.infrastructure.implementation.dev.order_generator import generate_labeled_orders
from app.infrastructure.repository.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from app.infrastructure.repository.mongo_order_repository import (
    LABEL_FIELD,
    MongoOrderRepository,
)


@pytest.fixture(params=["memory", "mongo"])
def repository(request):
    """Chaque test de contrat tourne sur les deux implémentations."""
    if request.param == "memory":
        return InMemoryOrderRepository()
    return MongoOrderRepository(FakeMongoCollection())


def with_id(order, order_id):
    return dataclasses.replace(order, order_id=order_id)


# --- Contrat commun ---


def test_saved_order_can_be_read_back(repository, order):
    repository.save(order, 1)

    assert repository.get(order.order_id) == order


def test_get_returns_none_for_an_unknown_id(repository):
    assert repository.get("CMD-INCONNUE") is None


def test_save_rejects_an_order_without_id(repository, order):
    with pytest.raises(ValueError, match="order_id"):
        repository.save(with_id(order, None), 1)


def test_saving_the_same_id_replaces_the_order(repository, order):
    repository.save(order, 1)
    updated = dataclasses.replace(order, distance_km=42.0)
    repository.save(updated, 0)

    assert repository.get(order.order_id) == updated
    assert repository.get_training_data() == ([updated], [0])


def test_training_data_keeps_orders_and_labels_aligned(repository, order):
    orders = [with_id(order, f"CMD-{index}") for index in range(3)]
    for order_to_save, label in zip(orders, [1, 0, 1]):
        repository.save(order_to_save, label)

    training_orders, labels = repository.get_training_data()

    assert dict(zip([o.order_id for o in training_orders], labels)) == {
        "CMD-0": 1,
        "CMD-1": 0,
        "CMD-2": 1,
    }


# --- En mémoire ---


def test_in_memory_repository_accepts_initial_orders():
    orders, labels = generate_labeled_orders(n_rows=50, random_state=42)

    assert InMemoryOrderRepository(orders, labels).get_training_data() == (orders, labels)


def test_in_memory_repository_rejects_mismatched_labels(order):
    with pytest.raises(ValueError, match="labels"):
        InMemoryOrderRepository([order], [1, 0])


# --- MongoDB : documents écrits par l'ETL de l'ERP ---


def erp_document(order, **changes):
    """Document tel que l'ETL l'écrit : variables, label, et champs propres à l'ERP."""
    document = {
        **dataclasses.asdict(order),
        LABEL_FIELD: 1,
        "_id": "ObjectId",
        "order_date": "2026-10-29T00:00:00",
    }
    return {**document, **changes}


def test_mongo_ignores_erp_fields_and_reads_the_label(order):
    repository = MongoOrderRepository(FakeMongoCollection([erp_document(order)]))

    assert repository.get_training_data() == ([order], [1])


def test_mongo_training_data_skips_orders_without_label(order):
    documents = [erp_document(order)]
    unlabeled = erp_document(with_id(order, "CMD-SANS-LABEL"))
    del unlabeled[LABEL_FIELD]
    documents.append(unlabeled)
    repository = MongoOrderRepository(FakeMongoCollection(documents))

    orders, labels = repository.get_training_data()

    assert [o.order_id for o in orders] == [order.order_id]


@pytest.mark.parametrize(
    "invalid",
    [
        {"preparation_time_min": None},
        {"distance_km": "loin"},
        {"weather": 3},
        {"hour": 14.5},
    ],
)
def test_mongo_training_data_rejects_invalid_documents(order, invalid, caplog):
    documents = [erp_document(order), erp_document(with_id(order, "CMD-INVALIDE"), **invalid)]
    repository = MongoOrderRepository(FakeMongoCollection(documents))

    orders, labels = repository.get_training_data()

    assert [o.order_id for o in orders] == [order.order_id]
    assert labels == [1]
    assert "1 commande(s) invalide(s)" in caplog.text


def test_mongo_converts_numbers_to_the_entity_types(order):
    document = erp_document(order, hour=14.0, distance_km=3)
    repository = MongoOrderRepository(FakeMongoCollection([document]))

    read = repository.get(order.order_id)

    assert type(read.hour) is int
    assert type(read.distance_km) is float


# --- Choix de l'implémentation ---


def test_memory_url_builds_a_repository_with_synthetic_orders(settings):
    orders, labels = build_order_repository(settings).get_training_data()

    assert len(orders) == len(labels) == 6000


def test_unknown_url_is_refused(settings):
    settings.training_source_url = "postgresql://localhost/commandes"

    with pytest.raises(ValueError, match="TRAINING_SOURCE_URL"):
        build_order_repository(settings)
