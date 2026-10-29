"""Configuration de l'application, lue depuis l'environnement.

Ce fichier implémente le principe « la configuration vient de l'environnement »
(12-factor) : aucun secret, aucune URL de base de données et aucun chemin de modèle
n'est écrit en dur dans le code métier. Les valeurs sont lues depuis l'environnement
ou depuis un fichier `.env` (voir `.env.example`), dans cet ordre de priorité.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application.

    Les noms de champs correspondent aux clés de `.env.example`. Avec
    `SettingsConfigDict(env_file=".env")`, pydantic lit les variables d'environnement
    en priorité sur le fichier `.env`. Une clé vide (`MODEL_THRESHOLD=`) prend la
    valeur par défaut.

    Elle est créée une seule fois par point d'entrée, puis passée aux classes qui en
    ont besoin : aucune classe métier ne lit la configuration elle-même.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    # Graine aléatoire
    random_seed: int = 42
    # Chemin du .joblib écrit par la cellule 41 du notebook.
    model_path: str = "notebooks/artifacts/express_delivery_model.joblib"
    # Seuil de décision qui transforme une probabilité en oui/non (cellule 31).
    model_threshold: float = 0.5
    # DEBUG | INFO | WARNING | ERROR
    log_level: str = "INFO"
    # Version du modèle servi (provisoire, voir ADR-0002).
    model_version: str = "1.0.0"
    # Source des commandes de l'entraînement (ADR-0009) : `memory://` (données
    # synthétiques) ou `mongodb://hôte:27017/livraison_express` (commandes de l'ERP).
    training_source_url: str = "memory://"
    # Promotion (ADR-0010) : le nouveau modèle remplace le modèle en service seulement si
    # cette métrique, mesurée sur le même jeu de test, le dépasse d'au moins ce gain.
    promotion_metric: str = "f1_score"
    promotion_min_gain: float = 0.0
