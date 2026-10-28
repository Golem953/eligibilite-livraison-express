"""Contrat des variables du modèle : mêmes colonnes, même ordre, partout."""

from app.core.learning.order_feature import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    orders_to_dataframe,
)


def test_numeric_and_categorical_features_cover_all_features():
    assert sorted(NUMERIC_FEATURES + CATEGORICAL_FEATURES) == sorted(FEATURE_COLUMNS)


def test_dataframe_has_feature_columns_in_order(order):
    df = orders_to_dataframe([order])

    assert list(df.columns) == FEATURE_COLUMNS
    assert len(df) == 1


def test_dataframe_keeps_order_values(order):
    row = orders_to_dataframe([order]).iloc[0]

    assert row["distance_km"] == order.distance_km
    assert row["delivery_zone"] == order.delivery_zone


def test_order_id_is_not_a_feature(order):
    df = orders_to_dataframe([order])

    assert "order_id" not in df.columns
