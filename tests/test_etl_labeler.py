"""ETL simulé, mode `label` : labellisation des commandes écrites par l'ERP (ADR-0010).

L'ETL n'est pas un paquet de l'application : il est importé depuis son dossier.
"""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl_simulator"))

from etl_simulator import LABEL_FIELD, LabeledOrderGenerator, labels_for  # noqa: E402


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
