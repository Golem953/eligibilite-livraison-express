"""Génère des commandes fictives (repris du notebook d'exploration) et les
enregistre dans la base configurée par DATABASE_URL.

Usage :
    python tools/generate_orders.py
    python tools/generate_orders.py --rows 1000 --seed 7

Au lancement, l'outil demande s'il faut vider la base avant d'insérer, ou
ajouter les commandes aux données existantes.
"""

import argparse
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from domain.entities.order import Order, OrderStatus
from infrastructure.adapter.dependency_injection.container import (
    get_order_repository,
)
from infrastructure.config.settings import get_settings


class GenerateOrders:
    """
    Classe pour générer un jeu de données fictif représentant des commandes.
    Le jeu de données est volontairement synthétique afin que le projet
    soit exécutable sans source externe.
    """

    def __init__(self, n_rows=6000, random_state=42, id_prefix="CMD-"):
        self.n_rows = n_rows
        self.random_state = random_state
        self.id_prefix = id_prefix

    def generate(self) -> pd.DataFrame:
        n_rows = self.n_rows
        rng = np.random.default_rng(self.random_state)

        order_date = pd.date_range(start="2025-01-01", end="2025-12-31", periods=n_rows)

        hour = rng.integers(7, 23, size=n_rows)
        day_of_week = pd.Series(order_date).dt.dayofweek.to_numpy()
        weekend = (day_of_week >= 5).astype(int)

        data = pd.DataFrame(
            {
                "order_id": [f"{self.id_prefix}{i:06d}" for i in range(1, n_rows + 1)],
                "order_date": order_date,
                "hour": hour,
                "day_of_week": day_of_week,
                "weekend": weekend,
                "distance_km": np.round(
                    rng.gamma(shape=2.0, scale=4.0, size=n_rows), 2
                ),
                "order_value_eur": np.round(rng.uniform(10, 250, size=n_rows), 2),
                "weight_kg": np.round(rng.uniform(0.2, 25, size=n_rows), 2),
                "stock_available": rng.binomial(1, 0.85, size=n_rows),
                "preparation_time_min": np.round(
                    rng.normal(loc=25, scale=10, size=n_rows).clip(5, 90), 1
                ),
                "carrier_capacity": np.round(rng.uniform(0.2, 1.0, size=n_rows), 2),
                "weather": rng.choice(
                    ["normal", "pluie", "neige", "orage"],
                    size=n_rows,
                    p=[0.65, 0.20, 0.10, 0.05],
                ),
                "delivery_zone": rng.choice(
                    ["centre", "proche_banlieue", "banlieue", "rurale"],
                    size=n_rows,
                    p=[0.30, 0.30, 0.25, 0.15],
                ),
                "customer_type": rng.choice(
                    ["standard", "premium"], size=n_rows, p=[0.80, 0.20]
                ),
            }
        )

        # Coefficient de difficulté lié à la zone de livraison
        zone_penalty = data["delivery_zone"].map(
            {"centre": 0, "proche_banlieue": 0.10, "banlieue": 0.25, "rurale": 0.45}
        )

        weather_penalty = data["weather"].map(
            {"normal": 0, "pluie": 0.10, "neige": 0.25, "orage": 0.30}
        )

        customer_bonus = (data["customer_type"] == "premium").astype(int) * 0.15

        # Score latent simulant une décision métier
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

        return data


def to_orders(data: pd.DataFrame) -> list[Order]:
    """Convertit les lignes générées en commandes historiques : label réel
    connu, pas de prédiction (statut « labellisée »)."""
    return [
        Order(
            order_id=row.order_id,
            # Le générateur produit des dates sans fuseau : on les considère en UTC.
            order_date=row.order_date.to_pydatetime().replace(tzinfo=UTC),
            hour=int(row.hour),
            day_of_week=int(row.day_of_week),
            weekend=bool(row.weekend),
            distance_km=float(row.distance_km),
            order_value_eur=float(row.order_value_eur),
            weight_kg=float(row.weight_kg),
            stock_available=bool(row.stock_available),
            preparation_time_min=float(row.preparation_time_min),
            carrier_capacity=float(row.carrier_capacity),
            weather=row.weather,
            delivery_zone=row.delivery_zone,
            customer_type=row.customer_type,
            status=OrderStatus.LABELLED,
            real_label=bool(row.express_eligible),
        )
        for row in data.itertuples(index=False)
    ]


def ask_mode() -> str | None:
    """Renvoie « vider », « ajouter », ou None si l'utilisateur annule."""
    print("Que faire des commandes déjà présentes dans la base ?")
    print("  1. Vider la base, puis insérer les nouvelles commandes")
    print("  2. Ajouter les nouvelles commandes aux données existantes")
    print("  3. Annuler")
    choices = {"1": "vider", "2": "ajouter", "3": None}
    while True:
        try:
            answer = input("Votre choix [1/2/3] : ").strip()
        except EOFError:  # pas de clavier (CI, Docker…)
            return None
        if answer in choices:
            return choices[answer]
        print("Réponse invalide, tapez 1, 2 ou 3.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère des commandes fictives.")
    parser.add_argument("--rows", type=int, default=6000, help="nombre de commandes")
    parser.add_argument("--seed", type=int, default=42, help="graine aléatoire")
    args = parser.parse_args()

    print(f"Base cible : {get_settings().database_url}")
    mode = ask_mode()
    if mode is None:
        print("Annulé, la base n'a pas été modifiée.")
        return

    # En ajout, un préfixe propre à ce lancement évite les identifiants en double.
    id_prefix = "CMD-" if mode == "vider" else f"CMD-{datetime.now(UTC):%Y%m%d%H%M%S}-"
    data = GenerateOrders(args.rows, args.seed, id_prefix).generate()
    orders = to_orders(data)

    repository = get_order_repository()
    if mode == "vider":
        repository.delete_all()
    repository.save_all(orders)
    print(f"{len(orders)} commandes enregistrées (mode : {mode}).")


if __name__ == "__main__":
    main()
