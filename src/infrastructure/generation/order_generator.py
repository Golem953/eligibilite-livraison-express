import numpy as np
import pandas as pd


class OrderGenerator:
    @staticmethod
    def generate_orders_dataset(n_rows=6000, random_state=42):
        """
        Génère un jeu de données fictif représentant des commandes.
        Le jeu de données est volontairement synthétique afin que le notebook
        soit exécutable sans source externe.
        """
        rng = np.random.default_rng(random_state)

        order_date = pd.date_range(
            start="2025-01-01",
            end="2025-12-31",
            periods=n_rows
        )

        hour = rng.integers(7, 23, size=n_rows)
        day_of_week = pd.Series(order_date).dt.dayofweek.to_numpy()
        weekend = (day_of_week >= 5).astype(int)

        data = pd.DataFrame({
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
                1
            ),
            "carrier_capacity": np.round(
                rng.uniform(0.2, 1.0, size=n_rows),
                2
            ),
            "weather": rng.choice(
                ["normal", "pluie", "neige", "orage"],
                size=n_rows,
                p=[0.65, 0.20, 0.10, 0.05]
            ),
            "delivery_zone": rng.choice(
                ["centre", "proche_banlieue", "banlieue", "rurale"],
                size=n_rows,
                p=[0.30, 0.30, 0.25, 0.15]
            ),
            "customer_type": rng.choice(
                ["standard", "premium"],
                size=n_rows,
                p=[0.80, 0.20]
            ),
        })

        # Coefficient de difficulté lié à la zone de livraison
        zone_penalty = data["delivery_zone"].map({
            "centre": 0,
            "proche_banlieue": 0.10,
            "banlieue": 0.25,
            "rurale": 0.45,
        })

        weather_penalty = data["weather"].map({
            "normal": 0,
            "pluie": 0.10,
            "neige": 0.25,
            "orage": 0.30,
        })

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
