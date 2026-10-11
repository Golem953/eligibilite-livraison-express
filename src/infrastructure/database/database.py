"""Schéma de la base des commandes, identique en SQLite (dev) et PostgreSQL (prod).

Les tables sont créées au démarrage de l'API et des outils si elles n'existent pas.
Aucune fonctionnalité propre à un moteur : les contrôles sont des CHECK standards.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
)

metadata = MetaData()

orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("order_id", String(64), nullable=False, unique=True),
    Column("order_date", DateTime(timezone=True), nullable=False),
    Column("hour", Integer, nullable=False),
    Column("day_of_week", Integer, nullable=False),
    Column("weekend", Integer, nullable=False),
    Column("distance_km", Float, nullable=False),
    Column("order_value_eur", Float, nullable=False),
    Column("weight_kg", Float, nullable=False),
    Column("stock_available", Integer, nullable=False),
    Column("preparation_time_min", Float, nullable=False),
    Column("carrier_capacity", Float, nullable=False),
    Column("weather", String(16), nullable=False),
    Column("delivery_zone", String(32), nullable=False),
    Column("customer_type", String(16), nullable=False),
    # Résultat réel (label) : vide pour une commande reçue par l'API, tant que le
    # résultat n'est pas connu. L'entraînement ne lit que les lignes renseignées :
    # une prédiction n'est jamais utilisée comme label.
    Column("express_eligible", Integer, nullable=True),
    # Origine de la ligne : "api" ou "generated" (tools/generate_orders.py).
    Column("source", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("hour BETWEEN 0 AND 23", name="ck_orders_hour"),
    CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_orders_day_of_week"),
    CheckConstraint("weekend IN (0, 1)", name="ck_orders_weekend"),
    CheckConstraint("distance_km >= 0", name="ck_orders_distance_km"),
    CheckConstraint("order_value_eur >= 0", name="ck_orders_order_value_eur"),
    CheckConstraint("weight_kg >= 0", name="ck_orders_weight_kg"),
    CheckConstraint("stock_available IN (0, 1)", name="ck_orders_stock_available"),
    CheckConstraint(
        "preparation_time_min >= 0", name="ck_orders_preparation_time_min"
    ),
    CheckConstraint(
        "carrier_capacity BETWEEN 0 AND 1", name="ck_orders_carrier_capacity"
    ),
    CheckConstraint(
        "weather IN ('normal', 'pluie', 'neige', 'orage')", name="ck_orders_weather"
    ),
    CheckConstraint(
        "delivery_zone IN ('centre', 'proche_banlieue', 'banlieue', 'rurale')",
        name="ck_orders_delivery_zone",
    ),
    CheckConstraint(
        "customer_type IN ('standard', 'premium')", name="ck_orders_customer_type"
    ),
    CheckConstraint(
        "express_eligible IS NULL OR express_eligible IN (0, 1)",
        name="ck_orders_express_eligible",
    ),
    CheckConstraint("source IN ('api', 'generated')", name="ck_orders_source"),
)

predictions = Table(
    "predictions",
    metadata,
    Column(
        "order_id",
        String(64),
        ForeignKey("orders.order_id"),
        primary_key=True,
    ),
    Column("express_eligible", Boolean, nullable=False),
    Column("decision", String(3), nullable=False),
    Column("probability", Float, nullable=False),
    Column("model_version", String(32), nullable=False),
    Column("predicted_at", DateTime(timezone=True), nullable=False),
    Column("latency_ms", Float, nullable=True),
    CheckConstraint("decision IN ('oui', 'non')", name="ck_predictions_decision"),
    CheckConstraint(
        "probability BETWEEN 0 AND 1", name="ck_predictions_probability"
    ),
)


class Database:
    def __init__(self, database_url):
        self.engine = create_engine(database_url, pool_pre_ping=True)

        if self.engine.dialect.name == "sqlite":
            # SQLite ignore les clés étrangères sans ce réglage, à chaque connexion.
            @event.listens_for(self.engine, "connect")
            def _enable_foreign_keys(dbapi_connection, _record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.close()

    def create_tables(self):
        metadata.create_all(self.engine)
