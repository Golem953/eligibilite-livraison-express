import pandas as pd

from domain.entities.order import Order

# Colonnes du jeu de données du notebook, lues sur l'entité Order.
ORDER_COLUMNS = [
    "order_id",
    "order_date",
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


class OrdersToDataframe:
    """Convertit des commandes en DataFrame au format du notebook : booléens en
    0 / 1, label réel dans la colonne cible `express_eligible`."""

    def __init__(self, orders: list[Order]):
        self.orders = orders

    def convert(self) -> pd.DataFrame:
        rows = []
        for order in self.orders:
            row = {
                column: _to_notebook_value(getattr(order, column))
                for column in ORDER_COLUMNS
            }
            row["express_eligible"] = _to_notebook_value(order.real_label)
            rows.append(row)
        return pd.DataFrame(rows, columns=[*ORDER_COLUMNS, "express_eligible"])


def _to_notebook_value(value: object) -> object:
    return int(value) if isinstance(value, bool) else value
