from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd
from sqlalchemy import bindparam, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from domain.ml_feature import FEATURE_COLUMNS, TARGET_COLUMN
from infrastructure.database.database import orders, predictions

TEMPORARY_ID_PREFIX = "tmp-"


class OrderRejectedError(Exception):
    """Commande refusée par la base : identifiant déjà pris ou contrainte violée."""


class OrderRepository:
    def __init__(self, database):
        self.engine = database.engine

    def ping(self):
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def add_order(self, features, order_id=None):
        """Enregistre une commande et renvoie son identifiant (CMD-000001…)."""
        return self.add_orders([{**features, "order_id": order_id}])[0]

    def add_orders(self, orders_features):
        """Enregistre des commandes en une transaction, renvoie leurs identifiants.

        Chaque commande porte ses variables et, en option, son order_id.
        """
        now = datetime.now(UTC)
        rows = [
            {
                **{feature: order[feature] for feature in FEATURE_COLUMNS},
                "order_id": order.get("order_id"),
                "order_date": now,
            }
            for order in orders_features
        ]
        return self._insert_orders(rows, "api")

    def add_generated_orders(self, df):
        """Enregistre des commandes générées, avec leur label. Renvoie le nombre."""
        rows = df[["order_date", *FEATURE_COLUMNS, TARGET_COLUMN]].to_dict("records")
        # Les identifiants du générateur repartent toujours de CMD-000001 : la base
        # attribue les siens, à la suite des commandes existantes.
        for row in rows:
            row["order_id"] = None
        return len(self._insert_orders(rows, "generated"))

    def _insert_orders(self, rows, source):
        now = datetime.now(UTC)
        for row in rows:
            row["source"] = source
            row["created_at"] = now
            row.setdefault(TARGET_COLUMN, None)
            if row["order_id"] is None:
                row["order_id"] = f"{TEMPORARY_ID_PREFIX}{uuid4().hex}"

        try:
            with self.engine.begin() as connection:
                inserted = connection.execute(
                    insert(orders).returning(
                        orders.c.id, orders.c.order_id, sort_by_parameter_order=True
                    ),
                    rows,
                ).all()

                # Identifiant serveur tiré de la clé auto-incrémentée : CMD-000042.
                renamed = [
                    {"row_id": row_id, "new_order_id": f"CMD-{row_id:06d}"}
                    for row_id, order_id in inserted
                    if order_id.startswith(TEMPORARY_ID_PREFIX)
                ]
                if renamed:
                    connection.execute(
                        update(orders)
                        .where(orders.c.id == bindparam("row_id"))
                        .values(order_id=bindparam("new_order_id")),
                        renamed,
                    )
        except IntegrityError as error:
            raise OrderRejectedError(str(error.orig)) from error

        new_ids = {item["row_id"]: item["new_order_id"] for item in renamed}
        return [new_ids.get(row_id, order_id) for row_id, order_id in inserted]

    def get_order(self, order_id):
        query = select(orders.c.order_id, *[orders.c[f] for f in FEATURE_COLUMNS])
        with self.engine.connect() as connection:
            row = connection.execute(
                query.where(orders.c.order_id == order_id)
            ).mappings().first()
        return dict(row) if row else None

    def save_predictions(self, saved_predictions):
        """Enregistre des prédictions (dictionnaires avec leur order_id)."""
        with self.engine.begin() as connection:
            connection.execute(insert(predictions), saved_predictions)

    def get_prediction(self, order_id):
        with self.engine.connect() as connection:
            row = connection.execute(
                select(predictions).where(predictions.c.order_id == order_id)
            ).mappings().first()
        if row is None:
            return None
        prediction = dict(row)
        # SQLite ne conserve pas le fuseau horaire : les dates sont stockées en UTC.
        if prediction["predicted_at"].tzinfo is None:
            prediction["predicted_at"] = prediction["predicted_at"].replace(tzinfo=UTC)
        return prediction

    def load_training_data(self):
        """Commandes dont le résultat réel est connu, au format du notebook."""
        query = select(
            orders.c.order_id,
            orders.c.order_date,
            *[orders.c[f] for f in FEATURE_COLUMNS],
            orders.c[TARGET_COLUMN],
        ).where(orders.c[TARGET_COLUMN].is_not(None))
        with self.engine.connect() as connection:
            return pd.read_sql(query, connection)

    def count_orders(self):
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(orders)).scalar()
