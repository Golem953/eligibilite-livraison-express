"""ETL simulé (ADR-0010) : il joue un système externe, pas l'application.

L'ERP alimente le MongoDB des analystes avec ses commandes, mais sans leur label
(`express_eligible`) : le résultat réel d'une livraison n'est connu qu'après coup.
Ce programme simule ce qui manque, avec la règle métier cachée du notebook, au format
de l'ERP (mêmes champs, mêmes valeurs : `clear`, `suburb`, `business`...).

Deux modes, choisis par `MODE` :

- `generate` (par défaut, dev et test) : il n'y a pas d'ERP. Le programme invente
  les commandes, déjà labellisées, et les écrit dans le MongoDB de l'environnement ;
- `label` (prod simulée) : l'ERP simulé (`erp_prod_test`) écrit ses commandes dans le
  MongoDB des analystes. Le programme ajoute seulement `express_eligible` aux
  commandes qui n'en ont pas, toutes les `INTERVAL_SECONDS` secondes, sans toucher
  au reste du document.

L'application ne fait que lire le résultat avec `MongoOrderRepository`.

Scénario du mode `generate` :

1. un historique de commandes labellisées, du 1er janvier 2023 à hier ;
2. puis un lot de commandes toutes les `INTERVAL_SECONDS` secondes, chaque lot
   portant la date du jour suivant (le scénario n'attend pas le calendrier réel).

Les commandes sont déterministes (même numéro, même commande) et écrites par upsert
sur `order_id` : relancer le simulateur ne crée pas de doublon.
"""

from __future__ import annotations

import logging
import math
import os
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from pymongo import DESCENDING, MongoClient, ReplaceOne, UpdateOne

logger = logging.getLogger("etl_simulator")

COLLECTION_NAME = "orders"
LABEL_FIELD = "express_eligible"
HISTORY_START = date(2023, 1, 1)
MODES = ("generate", "label")
# Variables utilisées par la règle métier : sans l'une d'elles, pas de label.
RULE_FIELDS = (
    "hour",
    "weekend",
    "distance_km",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
    "weather",
    "delivery_zone",
    "customer_type",
)

Order = dict[str, object]


@dataclass(frozen=True)
class EtlConfig:
    """Réglages lus dans l'environnement. `LIVE_ORDER_LIMIT=0` : flux illimité."""

    mongo_uri: str
    history_orders: int
    batch_size: int
    interval_seconds: float
    live_order_limit: int
    mode: str = "generate"

    @classmethod
    def from_env(cls) -> EtlConfig:
        return cls(
            mongo_uri=os.environ["MONGO_URI"],
            history_orders=int(os.environ.get("HISTORY_ORDERS", "3000")),
            batch_size=int(os.environ.get("BATCH_SIZE", "5")),
            interval_seconds=float(os.environ.get("INTERVAL_SECONDS", "5")),
            live_order_limit=int(os.environ.get("LIVE_ORDER_LIMIT", "0")),
            mode=os.environ.get("MODE", "generate"),
        )


class LabeledOrderGenerator:
    """Commandes au format de l'ERP, avec le label qu'un vrai ETL y ajouterait."""

    ZONE_PENALTY = {"centre": 0.0, "suburb": 0.25, "rural": 0.6}
    WEATHER_PENALTY = {"clear": 0.0, "rain": 0.15, "wind": 0.2, "snow": 0.4}

    def build(self, sequence: int, order_date: date) -> Order:
        rng = random.Random(sequence)
        order: Order = {
            "order_id": f"ERP-{sequence:08d}",
            "order_date": datetime.combine(order_date, datetime.min.time()),
            "hour": 8 + sequence % 12,
            "day_of_week": order_date.weekday(),
            "weekend": int(order_date.weekday() >= 5),
            "distance_km": round(rng.uniform(1, 40), 2),
            "order_value_eur": round(rng.uniform(15, 250), 2),
            "weight_kg": round(rng.uniform(0.2, 25), 2),
            "stock_available": rng.randint(0, 1),
            "preparation_time_min": round(rng.uniform(5, 45), 2),
            "carrier_capacity": round(rng.uniform(5, 50), 2),
            "weather": rng.choice(list(self.WEATHER_PENALTY)),
            "delivery_zone": rng.choice(list(self.ZONE_PENALTY)),
            "customer_type": rng.choice(["individual", "business"]),
        }
        order[LABEL_FIELD] = int(rng.random() < self._probability(order))
        return order

    def history(self, count: int, today: date) -> list[Order]:
        """`count` commandes réparties du 1er janvier 2023 à hier, numérotées à partir de 1."""
        span_days = (today - HISTORY_START).days
        if count <= 0 or span_days <= 0:
            return []
        return [
            self.build(sequence, HISTORY_START + timedelta(days=(sequence - 1) % span_days))
            for sequence in range(1, count + 1)
        ]

    def batch(self, first_sequence: int, size: int, order_date: date) -> list[Order]:
        return [
            self.build(sequence, order_date)
            for sequence in range(first_sequence, first_sequence + size)
        ]

    def label(self, order: Order) -> int | None:
        """Label d'une commande de l'ERP, ou `None` si la règle ne peut pas s'appliquer.

        Tiré à partir de l'`order_id` : relabelliser une commande donne toujours le même
        label, même si l'ERP l'a réécrite entre-temps.
        """
        if any(order.get(field) is None for field in RULE_FIELDS):
            return None
        if order["weather"] not in self.WEATHER_PENALTY:
            return None
        if order["delivery_zone"] not in self.ZONE_PENALTY:
            return None
        return int(random.Random(order["order_id"]).random() < self._probability(order))

    def _probability(self, order: Order) -> float:
        """Règle métier simulée : plus la commande est loin, lourde ou longue à préparer, moins l'express est possible."""
        score = (
            2.5
            - 0.08 * order["distance_km"]
            - 0.035 * order["preparation_time_min"]
            - 0.035 * order["weight_kg"]
            - self.ZONE_PENALTY[order["delivery_zone"]]
            - self.WEATHER_PENALTY[order["weather"]]
            + 1.8 * order["stock_available"]
            + 0.03 * order["carrier_capacity"]
            + 0.2 * (order["customer_type"] == "business")
            - 0.4 * order["weekend"]
            - 0.08 * max(order["hour"] - 18, 0)
        )
        return 1 / (1 + math.exp(-score))


class MongoLoader:
    """Étape « load » : écrit les commandes labellisées dans la collection `orders`."""

    def __init__(self, uri: str):
        self._client = MongoClient(uri)
        self._client.admin.command("ping")
        self._collection = self._client.get_default_database()[COLLECTION_NAME]
        self._collection.create_index("order_id", unique=True)

    def load(self, orders: list[Order]) -> int:
        if not orders:
            return 0
        result = self._collection.bulk_write(
            [ReplaceOne({"order_id": order["order_id"]}, order, upsert=True) for order in orders]
        )
        return result.upserted_count + result.modified_count

    def unlabeled(self) -> list[Order]:
        """Commandes écrites par l'ERP qui n'ont pas encore de label."""
        return list(self._collection.find({LABEL_FIELD: {"$exists": False}}))

    def set_labels(self, labels: dict[str, int]) -> int:
        """Ajoute le label aux commandes, sans réécrire le reste du document."""
        if not labels:
            return 0
        result = self._collection.bulk_write(
            [
                UpdateOne({"order_id": order_id}, {"$set": {LABEL_FIELD: label}})
                for order_id, label in labels.items()
            ]
        )
        return result.modified_count

    def last_sequence(self) -> int:
        last = self._collection.find_one({}, {"order_id": 1}, sort=[("order_id", DESCENDING)])
        return int(last["order_id"].removeprefix("ERP-")) if last else 0

    def close(self) -> None:
        self._client.close()


def run(config: EtlConfig, generator: LabeledOrderGenerator, loader: MongoLoader) -> None:
    today = date.today()
    history = generator.history(config.history_orders, today)
    logger.info("Historique 2023 -> hier : %d commandes chargées", loader.load(history))

    sequence = max(loader.last_sequence(), config.history_orders) + 1
    order_date = today
    written = 0
    while config.live_order_limit == 0 or written < config.live_order_limit:
        size = config.batch_size
        if config.live_order_limit:
            size = min(size, config.live_order_limit - written)
        batch = generator.batch(sequence, size, order_date)
        loader.load(batch)
        logger.info("Lot du %s : %d commandes labellisées chargées", order_date, len(batch))
        sequence += size
        written += size
        order_date += timedelta(days=1)
        time.sleep(config.interval_seconds)


def labels_for(orders: list[Order], generator: LabeledOrderGenerator) -> dict[str, int]:
    """Labels des commandes que la règle peut traiter, indexés par `order_id`."""
    labels = {}
    for order in orders:
        label = generator.label(order)
        if label is not None:
            labels[order["order_id"]] = label
    return labels


def label_forever(config: EtlConfig, generator: LabeledOrderGenerator, loader: MongoLoader) -> None:
    """Mode `label` : labellise les nouvelles commandes de l'ERP, en continu."""
    while True:
        pending = loader.unlabeled()
        labels = labels_for(pending, generator)
        written = loader.set_labels(labels)
        if pending:
            logger.info(
                "Labellisation : %d commandes labellisées, %d ignorées (variable absente ou inconnue)",
                written,
                len(pending) - len(labels),
            )
        time.sleep(config.interval_seconds)


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # En DEBUG, pymongo journalise chaque connexion : seuls ses avertissements nous intéressent.
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    config = EtlConfig.from_env()
    if config.mode not in MODES:
        raise ValueError(f"MODE doit valoir {' ou '.join(MODES)}, pas {config.mode!r}")
    loader = MongoLoader(config.mongo_uri)
    try:
        if config.mode == "label":
            label_forever(config, LabeledOrderGenerator(), loader)
        else:
            run(config, LabeledOrderGenerator(), loader)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
