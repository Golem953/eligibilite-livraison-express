"""Remplit la base avec des commandes fictives (génération reprise du notebook).

Les commandes sont historiques : label réel connu, pas de prédiction (statut
« labellisée »). Elles servent de jeu d'entraînement. Les identifiants sont
tirés du même compteur que l'API (CMD-000001…), donc jamais en double : chaque
lancement ajoute des commandes. Pour repartir de zéro, supprimer la base
(fichier SQLite, ou volume PostgreSQL avec docker compose down -v).

Usage (depuis la racine du dépôt, venv activé) :
    python tools/generate_orders.py
    python tools/generate_orders.py --rows 1000 --seed 7
La base visée est DATABASE_URL (par défaut sqlite:///data/commandes.db).
"""

import argparse
import os
from datetime import UTC, datetime, timedelta

import numpy as np

from domain.entities.order import Order
from domain.value_objects.customer_type import CustomerType
from domain.value_objects.delivery_zone import DeliveryZone
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.weather import Weather
from infrastructure.adapter.dependency_injection.container import (
    DEFAULT_DATABASE_URL,
    build_connector,
)
from infrastructure.repository.sql_order_id_generator import SqlOrderIdGenerator
from infrastructure.repository.sql_order_repository import SqlOrderRepository

_ZONE_PENALTY = {"centre": 0, "proche_banlieue": 0.10, "banlieue": 0.25, "rurale": 0.45}
_WEATHER_PENALTY = {"normal": 0, "pluie": 0.10, "neige": 0.25, "orage": 0.30}


def generate(n_rows: int, seed: int) -> list[dict]:
    """Variables et label de n_rows commandes, réparties sur l'année 2025."""
    rng = np.random.default_rng(seed)

    start = datetime(2025, 1, 1, tzinfo=UTC)
    span = datetime(2025, 12, 31, tzinfo=UTC) - start
    dates = [start + span * i / max(n_rows - 1, 1) for i in range(n_rows)]
    hour = rng.integers(7, 23, size=n_rows)
    day_of_week = np.array([date.weekday() for date in dates])
    weekend = (day_of_week >= 5).astype(int)

    distance_km = np.round(rng.gamma(shape=2.0, scale=4.0, size=n_rows), 2)
    order_value_eur = np.round(rng.uniform(10, 250, size=n_rows), 2)
    weight_kg = np.round(rng.uniform(0.2, 25, size=n_rows), 2)
    stock_available = rng.binomial(1, 0.85, size=n_rows)
    preparation_time_min = np.round(
        rng.normal(loc=25, scale=10, size=n_rows).clip(5, 90), 1
    )
    carrier_capacity = np.round(rng.uniform(0.2, 1.0, size=n_rows), 2)
    weather = rng.choice(
        list(_WEATHER_PENALTY), size=n_rows, p=[0.65, 0.20, 0.10, 0.05]
    )
    delivery_zone = rng.choice(
        list(_ZONE_PENALTY), size=n_rows, p=[0.30, 0.30, 0.25, 0.15]
    )
    customer_type = rng.choice(["standard", "premium"], size=n_rows, p=[0.80, 0.20])

    # Score latent simulant une décision métier (notebook).
    score = (
        2.5
        - 0.18 * distance_km
        - 0.035 * preparation_time_min
        - 0.035 * weight_kg
        - np.array([_ZONE_PENALTY[zone] for zone in delivery_zone])
        - np.array([_WEATHER_PENALTY[w] for w in weather])
        + 1.8 * stock_available
        + 1.3 * carrier_capacity
        + 0.15 * (customer_type == "premium")
        - 0.40 * weekend
        - 0.08 * np.maximum(hour - 18, 0)
    )
    express_eligible = rng.binomial(1, 1 / (1 + np.exp(-score)))

    return [
        {
            # L'heure tirée remplace celle de la date, pour rester cohérentes.
            "order_date": dates[i].replace(hour=int(hour[i]), minute=0, second=0)
            + timedelta(minutes=int(rng.integers(0, 60))),
            "hour": int(hour[i]),
            "day_of_week": int(day_of_week[i]),
            "weekend": bool(weekend[i]),
            "distance_km": float(distance_km[i]),
            "order_value_eur": float(order_value_eur[i]),
            "weight_kg": float(weight_kg[i]),
            "stock_available": bool(stock_available[i]),
            "preparation_time_min": float(preparation_time_min[i]),
            "carrier_capacity": float(carrier_capacity[i]),
            "weather": Weather(str(weather[i])),
            "delivery_zone": DeliveryZone(str(delivery_zone[i])),
            "customer_type": CustomerType(str(customer_type[i])),
            "real_label": bool(express_eligible[i]),
        }
        for i in range(n_rows)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Remplit la base de commandes.")
    parser.add_argument("--rows", type=int, default=6000, help="nombre de commandes")
    parser.add_argument("--seed", type=int, default=42, help="graine aléatoire")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    # Seul le moteur est affiché : l'URL complète contient le mot de passe.
    print(f"Base cible : {database_url.split('://', 1)[0]}")

    connector = build_connector(database_url)
    repository = SqlOrderRepository(connector)
    id_generator = SqlOrderIdGenerator(connector)

    rows = generate(args.rows, args.seed)
    for row in rows:
        # Order(...) direct et non OrderFactory : ce sont des commandes
        # historiques (date passée, label connu), pas de nouvelles commandes.
        repository.save(
            Order(order_id=id_generator.next_id(), status=OrderStatus.LABELLED, **row)
        )
    print(f"{len(rows)} commandes enregistrées.")


if __name__ == "__main__":
    main()
