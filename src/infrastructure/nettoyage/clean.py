import pandas as pd


class Clean:
    @staticmethod
    def clean_orders_data(df):
        """
        Nettoyage automatique des données.
        Cette fonction devra ensuite être utilisée dans la pipeline ETL.
        """
        cleaned = df.copy()

        # Suppression des doublons sur l'identifiant métier
        cleaned = cleaned.drop_duplicates(
            subset=["order_id"],
            keep="last"
        )

        # Conversion des dates
        cleaned["order_date"] = pd.to_datetime(
            cleaned["order_date"],
            errors="coerce"
        )

        # Suppression des lignes dont les champs essentiels sont invalides
        essential_columns = [
            "order_id",
            "distance_km",
            "weight_kg",
            "stock_available",
            "preparation_time_min",
            "carrier_capacity",
            "express_eligible",
        ]

        cleaned = cleaned.dropna(subset=essential_columns)

        # Bornage des valeurs numériques
        cleaned = cleaned[cleaned["distance_km"] >= 0]
        cleaned = cleaned[cleaned["weight_kg"] >= 0]
        cleaned = cleaned[cleaned["preparation_time_min"] >= 0]
        cleaned = cleaned[cleaned["carrier_capacity"].between(0, 1)]
        cleaned = cleaned[cleaned["stock_available"].isin([0, 1])]

        return cleaned.reset_index(drop=True)
