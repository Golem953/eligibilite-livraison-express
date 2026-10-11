from config.settings import PROJECT_NAME, THRESHOLD
from domain.ml_feature import FEATURE_COLUMNS, TARGET_COLUMN


class ModelCard:
    @staticmethod
    def build_model_card(loaded_model):
        """Model card de la cellule 55 du notebook, pour la version servie."""
        return {
            "project": PROJECT_NAME,
            "model_version": loaded_model.version,
            "model_type": "Régression logistique",
            "task": "Classification binaire",
            "target": TARGET_COLUMN,
            "threshold": THRESHOLD,
            "trained_at": loaded_model.trained_at,
            "features": FEATURE_COLUMNS,
            "metrics": loaded_model.metrics,
            "limitations": [
                "Le jeu de données utilisé est synthétique.",
                "La décision ne doit pas être utilisée sans validation des règles "
                "métier.",
                "Les performances peuvent varier sur des données réelles.",
                "Le modèle ne remplace pas une analyse des contraintes "
                "opérationnelles.",
            ],
        }
