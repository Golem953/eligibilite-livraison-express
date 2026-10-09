import pandas as pd

from infrastructure.config.training_config import QualityConfig


class CleanDataset:
    def __init__(self, data, quality: QualityConfig):
        self.data = data
        self.quality = quality

    def clean(self):
        """
        Nettoyage automatique des données.
        Les règles (champs essentiels, bornes, valeurs autorisées) viennent de
        la section [quality] de training.toml.
        """
        quality = self.quality
        cleaned = self.data.copy()

        # Suppression des doublons sur l'identifiant métier
        cleaned = cleaned.drop_duplicates(subset=[quality.id_column], keep="last")

        # Conversion des dates
        cleaned[quality.date_column] = pd.to_datetime(
            cleaned[quality.date_column], errors="coerce"
        )

        # Suppression des lignes dont les champs essentiels sont invalides
        cleaned = cleaned.dropna(subset=quality.essential_columns)

        # Bornage des valeurs numériques
        for column, bounds in quality.bounds.items():
            if bounds.min is not None:
                cleaned = cleaned[cleaned[column] >= bounds.min]
            if bounds.max is not None:
                cleaned = cleaned[cleaned[column] <= bounds.max]
        for column, allowed in quality.allowed_values.items():
            cleaned = cleaned[cleaned[column].isin(allowed)]

        return cleaned.reset_index(drop=True)
