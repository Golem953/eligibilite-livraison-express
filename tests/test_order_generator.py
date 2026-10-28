"""Générateur de données synthétiques : reproductible et exploitable pour l'entraînement."""

from app.infrastructure.implementation.dev.order_generator import generate_labeled_orders


def test_generates_requested_number_of_orders():
    orders, labels = generate_labeled_orders(n_rows=200, random_state=1)

    assert len(orders) == len(labels) == 200


def test_same_seed_gives_same_data():
    first = generate_labeled_orders(n_rows=100, random_state=7)
    second = generate_labeled_orders(n_rows=100, random_state=7)

    assert first == second


def test_different_seeds_give_different_data():
    first, _ = generate_labeled_orders(n_rows=100, random_state=1)
    second, _ = generate_labeled_orders(n_rows=100, random_state=2)

    assert first != second


def test_labels_are_binary_with_both_classes():
    _, labels = generate_labeled_orders(n_rows=500, random_state=3)

    assert set(labels) == {0, 1}


def test_order_ids_are_unique():
    orders, _ = generate_labeled_orders(n_rows=500, random_state=4)

    assert len({order.order_id for order in orders}) == 500
