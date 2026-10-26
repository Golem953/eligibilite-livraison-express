"""Générateur de commandes de développement.

`generate_orders_dataset()` du notebook synthétise 6 000 commandes avec une graine
fixe (`random_state=42`). C'est ce qui rend le notebook exécutable sans source de
données externe, et ce qui rend les tests et les entraînements reproductibles.

Le corps de la cellule 8 est déplacé **à l'identique** — même appel de générateur,
même ordre d'appels, même pondération du score, même sigmoïde — sous couvert de
`generate_labeled_orders()` : la logique de scoring est ce qui rend le jeu de données
apprenable. Une variation en ferait un autre jeu de données, et vos métriques ne
ressembleraient plus à celles du notebook (`accuracy ≈ 0.75`), sans qu'on sache
pourquoi.

Deux fonctions, une seule génération (DRY) :

- `generate_labeled_orders()` renvoie des commandes **et** leur étiquette
  (`express_eligible`) : c'est la source d'entraînement de `TrainEligibilityModel`,
  la cible n'ayant pas sa place dans `OrderFeatures` (on ne prédit pas ce qu'on
  connaît) ;
- `generate_orders_dataset()` applique la signature de la cellule 8, une liste de
  `OrderFeatures` sans étiquette : c'est ce qui peuple l'API en local et les tests.
  Le `DataFrame` pandas reste un détail de la génération : il ne sort pas d'ici.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.livraison_express_lite.domain.entities import OrderEntity


def generate_labeled_orders(
    n_rows: int = 6000, random_state: int = 42
) -> tuple[list[OrderEntity], list[int]]:
    """Générer des commandes **avec** l'étiquette d'éligibilité express (notebook cellule 8)."""
    rng = np.random.default_rng(random_state)

    order_date = pd.date_range(start="2025-01-01", end="2025-12-31", periods=n_rows)

    hour = rng.integers(7, 23, size=n_rows)
    day_of_week = pd.Series(order_date).dt.dayofweek.to_numpy()
    weekend = (day_of_week >= 5).astype(int)

    data = pd.DataFrame(
        {
            "order_id": [f"CMD-{i:06d}" for i in range(1, n_rows + 1)],
            "order_date": order_date,
            "hour": hour,
            "day_of_week": day_of_week,
            "weekend": weekend,
            "distance_km": np.round(rng.gamma(shape=2.0, scale=4.0, size=n_rows), 2),
            "order_value_eur": np.round(rng.uniform(10, 250, size=n_rows), 2),
            "weight_kg": np.round(rng.uniform(0.2, 25, size=n_rows), 2),
            "stock_available": rng.binomial(1, 0.85, size=n_rows),
            "preparation_time_min": np.round(
                rng.normal(loc=25, scale=10, size=n_rows).clip(5, 90),
                1,
            ),
            "carrier_capacity": np.round(rng.uniform(0.2, 1.0, size=n_rows), 2),
            "weather": rng.choice(
                ["normal", "pluie", "neige", "orage"], size=n_rows, p=[0.65, 0.20, 0.10, 0.05]
            ),
            "delivery_zone": rng.choice(
                ["centre", "proche_banlieue", "banlieue", "rurale"],
                size=n_rows,
                p=[0.30, 0.30, 0.25, 0.15],
            ),
            "customer_type": rng.choice(["standard", "premium"], size=n_rows, p=[0.80, 0.20]),
        }
    )

    # Coefficient de difficulté lié à la zone de livraison
    zone_penalty = data["delivery_zone"].map(
        {
            "centre": 0,
            "proche_banlieue": 0.10,
            "banlieue": 0.25,
            "rurale": 0.45,
        }
    )

    weather_penalty = data["weather"].map(
        {
            "normal": 0,
            "pluie": 0.10,
            "neige": 0.25,
            "orage": 0.30,
        }
    )

    customer_bonus = (data["customer_type"] == "premium").astype(int) * 0.15

    # Score simulant une décision métier
    score = (
        2.5
        - 0.18 * data["distance_km"]
        - 0.035 * data["preparation_time_min"]
        - 0.035 * data["weight_kg"]
        - zone_penalty
        - weather_penalty
        + 1.8 * data["stock_available"]
        + 1.3 * data["carrier_capacity"]
        + customer_bonus
        - 0.40 * data["weekend"]
        - 0.08 * np.maximum(data["hour"] - 18, 0)
    )

    probability = 1 / (1 + np.exp(-score))

    data["express_eligible"] = rng.binomial(1, probability)

    orders = [
        OrderEntity(
            order_id=row.order_id,
            hour=int(row.hour),
            day_of_week=int(row.day_of_week),
            weekend=int(row.weekend),
            distance_km=float(row.distance_km),
            order_value_eur=float(row.order_value_eur),
            weight_kg=float(row.weight_kg),
            stock_available=int(row.stock_available),
            preparation_time_min=float(row.preparation_time_min),
            carrier_capacity=float(row.carrier_capacity),
            weather=str(row.weather),
            delivery_zone=str(row.delivery_zone),
            customer_type=str(row.customer_type),
        )
        for row in data.itertuples(index=False)
    ]
    labels = data["express_eligible"].astype(int).tolist()
    return orders, labels


def generate_orders_dataset(n_rows: int = 6000, random_state: int = 42) -> list[OrderEntity]:
    """Générer des commandes **sans** l'étiquette d'éligibilité express.
    """
    orders, _labels = generate_labeled_orders(n_rows=n_rows, random_state=random_state)
    return orders
