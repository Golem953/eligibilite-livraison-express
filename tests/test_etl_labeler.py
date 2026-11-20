"""ETL simulé, mode `label` : labellisation des commandes écrites par l'ERP (ADR-0010).

L'ETL n'est pas un paquet de l'application : il est importé depuis son dossier.
"""

import os
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl_simulator"))

from etl_simulator import (  # noqa: E402
    LABEL_FIELD,
    LabeledOrderGenerator,
    MongoLoader,
    labels_for,
)

TEST_MONGO_URL = os.environ.get("TEST_MONGO_URL")


@pytest.fixture
def generator() -> LabeledOrderGenerator:
    return LabeledOrderGenerator()


def erp_order(generator, sequence: int) -> dict:
    """Commande telle que l'ERP l'écrit : les mêmes variables, sans label."""
    order = generator.build(sequence, date(2024, 3, 1))
    del order[LABEL_FIELD]
    return order


def test_label_is_0_or_1_and_stable(generator):
    order = erp_order(generator, 10_001)

    assert generator.label(order) in (0, 1)
    assert generator.label(order) == generator.label(dict(order))


def test_labels_follow_the_rule_not_a_constant(generator):
    orders = [erp_order(generator, sequence) for sequence in range(10_001, 11_001)]

    share = sum(labels_for(orders, generator).values()) / len(orders)

    assert 0.05 < share < 0.95


@pytest.mark.parametrize(
    "change",
    [{"preparation_time_min": None}, {"weekend": None}, {"weather": "tempête"}],
)
def test_order_the_rule_cannot_handle_is_left_unlabeled(generator, change):
    """Ancien schéma (variables à null) ou valeur inconnue : pas de label inventé."""
    order = erp_order(generator, 10_001) | change

    assert labels_for([order], generator) == {}


@pytest.mark.skipif(not TEST_MONGO_URL, reason="TEST_MONGO_URL absent : pas de MongoDB de test")
def test_labeler_on_real_mongo_only_adds_the_missing_labels(generator):
    """Vrai MongoDB : seules les commandes sans label sont lues, et seul le label est écrit."""
    loader = MongoLoader(TEST_MONGO_URL)
    collection = loader._collection
    collection.delete_many({})
    already = generator.build(1, date(2024, 3, 1)) | {LABEL_FIELD: 0, "_marker": "deja"}
    pending = erp_order(generator, 2) | {"_marker": "erp"}
    collection.insert_many([dict(already), dict(pending)])

    unlabeled = loader.unlabeled()
    written = loader.set_labels(labels_for(unlabeled, generator))

    assert [order["order_id"] for order in unlabeled] == [pending["order_id"]]
    assert written == 1
    stored = collection.find_one({"order_id": pending["order_id"]}, {"_id": 0})
    assert stored[LABEL_FIELD] == generator.label(pending)
    assert stored["_marker"] == "erp"
    assert collection.find_one({"order_id": already["order_id"]})[LABEL_FIELD] == 0
    assert loader.unlabeled() == []
    loader.close()
