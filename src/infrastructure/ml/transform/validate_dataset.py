from infrastructure.config.training_config import QualityConfig


class ValidateDataset:
    def __init__(self, dataset, quality: QualityConfig, target_column: str):
        self.dataset = dataset
        self.quality = quality
        self.target_column = target_column

    def validate(self):
        """
        Contrôles de qualité élémentaires sur les données d'entrée.
        Les règles (colonnes obligatoires, bornes, valeurs autorisées) viennent
        de la section [quality] de training.toml.
        """
        df = self.dataset
        quality = self.quality

        missing_columns = set(quality.required_columns) - set(df.columns)

        if missing_columns:
            raise ValueError(
                f"Colonnes obligatoires absentes : {sorted(missing_columns)}"
            )

        if df[quality.id_column].duplicated().any():
            raise ValueError("Des identifiants de commande sont dupliqués.")

        if df[self.target_column].isna().any():
            raise ValueError("La variable cible contient des valeurs manquantes.")

        for column, bounds in quality.bounds.items():
            if bounds.min is not None and not df[column].ge(bounds.min).all():
                raise ValueError(f"{column} : valeurs inférieures à {bounds.min}.")
            if bounds.max is not None and not df[column].le(bounds.max).all():
                raise ValueError(f"{column} : valeurs supérieures à {bounds.max}.")

        for column, allowed in quality.allowed_values.items():
            if not df[column].isin(allowed).all():
                raise ValueError(
                    f"La variable {column} doit contenir uniquement {allowed}."
                )

        return True
