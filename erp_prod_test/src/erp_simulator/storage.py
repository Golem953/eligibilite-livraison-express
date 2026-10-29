"""Adaptateurs de persistance du simulateur ERP."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Protocol, runtime_checkable

import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient, ReplaceOne

Order = dict[str, object]


class OrderWriter(Protocol):
    def write(self, orders: Sequence[Order]) -> int:
        """Écrit les commandes et renvoie le nombre de nouvelles commandes."""

    def close(self) -> None:
        """Libère les ressources de connexion."""


@runtime_checkable
class OrderCounter(Protocol):
    def count_from(self, start: date, end: date) -> int:
        """Compte les commandes sur une période."""

    def next_sequence(self) -> int:
        """Retourne le prochain numéro de commande disponible."""


class PostgresWriter:
    def __init__(self, dsn: str) -> None:
        self.connection = psycopg.connect(dsn, row_factory=dict_row)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY, order_date DATE, hour INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL, weekend INTEGER,
            distance_km DOUBLE PRECISION NOT NULL, order_value_eur DOUBLE PRECISION NOT NULL,
            weight_kg DOUBLE PRECISION NOT NULL, stock_available INTEGER NOT NULL,
            preparation_time_min DOUBLE PRECISION, carrier_capacity DOUBLE PRECISION NOT NULL,
            weather TEXT NOT NULL, delivery_zone TEXT NOT NULL, customer_type TEXT NOT NULL)"""
        )
        self.connection.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_date DATE")
        self.connection.execute("ALTER TABLE orders ALTER COLUMN weekend DROP NOT NULL")
        self.connection.execute("ALTER TABLE orders ALTER COLUMN preparation_time_min DROP NOT NULL")
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL)"""
        )
        self.connection.execute(
            """INSERT INTO schema_migrations (version, description) VALUES
            (2015, 'Ajout de la colonne weekend'),
            (2017, 'Ajout de la colonne preparation_time_min'),
            (2023, 'Extension du schéma pour le flux courant')
            ON CONFLICT (version) DO NOTHING"""
        )
        self.connection.commit()

    def write(self, orders: Sequence[Order]) -> int:
        inserted = 0
        with self.connection.transaction():
            for order in orders:
                columns = tuple(order)
                cursor = self.connection.execute(
                    f"INSERT INTO orders ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))}) ON CONFLICT (order_id) DO NOTHING",
                    tuple(order[column] for column in columns),
                )
                inserted += cursor.rowcount
        self.connection.commit()
        return inserted

    def count_from(self, start: date, end: date) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM orders WHERE order_date >= %s AND order_date < %s",
            (start, end),
        ).fetchone()
        self.connection.commit()
        return int(row["count"])

    def next_sequence(self) -> int:
        row = self.connection.execute(
            """SELECT COALESCE(MAX(
                CASE WHEN order_id ~ '^ERP-[0-9]+$'
                THEN SUBSTRING(order_id FROM 5)::BIGINT ELSE 0 END
            ), 0) AS max_sequence FROM orders"""
        ).fetchone()
        self.connection.commit()
        return int(row["max_sequence"])

    def close(self) -> None:
        self.connection.close()


class MongoWriter:
    def __init__(self, uri: str) -> None:
        self.client = MongoClient(uri)
        self.client.admin.command("ping")
        self.collection = self.client["livraison_express"]["orders"]
        self.collection.create_index("order_id", unique=True)

    @staticmethod
    def _document(order: Order) -> Order:
        document = dict(order)
        if isinstance(document.get("order_date"), date):
            document["order_date"] = datetime.combine(document["order_date"], time.min)
        return document

    def write(self, orders: Sequence[Order]) -> int:
        if not orders:
            return 0
        result = self.collection.bulk_write([
            ReplaceOne({"order_id": order["order_id"]}, self._document(order), upsert=True)
            for order in orders
        ])
        return result.upserted_count

    def close(self) -> None:
        self.client.close()
