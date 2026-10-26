"""Configuration de l'application, lue depuis l'environnement.

Ce fichier implémente le principe « la configuration vient de l'environnement »
(12-factor) : aucun secret, aucune URL de base de données et aucun chemin de modèle
n'est écrit en dur dans le code métier. Les valeurs sont lues depuis l'environnement
ou depuis un fichier `.env` (voir `.env.example`), dans cet ordre de priorité.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import logging


class Settings(BaseSettings):
    """Configuration de l'application.

    Les noms de champs correspondent aux clés de `.env.example`. Avec
    `SettingsConfigDict(env_file=".env")`, pydantic lit les variables d'environnement
    en priorité sur le fichier `.env`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Graine aléatoire
    random_seed: int = 42
    # local | test | prod
    environment: str = "local"
    # Chemin du .joblib écrit par la cellule 41 du notebook.
    model_path: str = "notebooks/artifacts/express_delivery_model.joblib"
    # URI MLflow du modèle à charger (ex. runs:/<run_id>/model).
    mlflow_model_uri: str = ""
    # Seuil de décision qui transforme une probabilité en oui/non (cellule 31).
    model_threshold: float = 0.5
    # Chaîne de connexion de l'implémentation d'OrderRepository retenue (ADR-0001).
    order_repository_url: str = "memory://"
    # DEBUG | INFO | WARNING | ERROR
    log_level: str = "INFO"
    # Version du modèle servi (provisoire, voir ADR-0002).
    model_version: str = "1.0.0"
