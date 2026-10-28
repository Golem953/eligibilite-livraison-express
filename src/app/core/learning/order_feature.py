from collections.abc import Iterable

import pandas as pd

from ...domain.entities import OrderEntity

TARGET_COLUMN = "express_eligible"

# Les identifiants et les dates brutes ne sont pas utilisés directement
# par le modèle dans cette première version.
FEATURE_COLUMNS = [
    "hour",
    "day_of_week",
    "weekend",
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
    "weather",
    "delivery_zone",
    "customer_type",
]

NUMERIC_FEATURES = [
    "hour",
    "day_of_week",
    "weekend",
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
]

CATEGORICAL_FEATURES = [
    "weather",
    "delivery_zone",
    "customer_type",
]


def orders_to_dataframe(orders: Iterable[OrderEntity]) -> pd.DataFrame:
    """Convertir des entités en table de features via leurs attributs.

    Le domaine reste indépendant de pandas : la conversion ne se fait qu'à la
    frontière avec la couche d'apprentissage.
    """
    return pd.DataFrame(
        [
            {feature: getattr(order, feature) for feature in FEATURE_COLUMNS}
            for order in orders
        ],
        columns=FEATURE_COLUMNS,
    )
