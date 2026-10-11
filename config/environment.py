"""Configuration lue dans le fichier .env (modèle : .env.example).

APP_ENV=dev : base SQLite (fichier data/commandes.db par défaut).
Toute autre valeur (prod) : base PostgreSQL construite avec les variables POSTGRES_*.

Les variables déjà présentes dans l'environnement (celles que docker compose passe
au conteneur) ont priorité sur le fichier .env.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "commandes.db"
DEFAULT_MLFLOW_TRACKING_URI = "http://localhost:5000"


@dataclass(frozen=True)
class Environment:
    app_env: str
    database_url: str
    mlflow_tracking_uri: str


def load_environment(app_env=None):
    """Lit .env puis construit la configuration.

    app_env force l'environnement (outils : --env prod), sinon APP_ENV est utilisé.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    app_env = app_env or os.getenv("APP_ENV", "dev")

    if app_env == "dev":
        sqlite_path = Path(os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH))
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{sqlite_path}"
    else:
        database_url = (
            "postgresql+psycopg://"
            f"{quote_plus(_required('POSTGRES_USER'))}"
            f":{quote_plus(_required('POSTGRES_PASSWORD'))}"
            f"@{os.getenv('POSTGRES_HOST', 'localhost')}"
            f":{os.getenv('POSTGRES_PORT', '5432')}"
            f"/{_required('POSTGRES_DB')}"
        )

    return Environment(
        app_env=app_env,
        database_url=database_url,
        mlflow_tracking_uri=os.getenv(
            "MLFLOW_TRACKING_URI", DEFAULT_MLFLOW_TRACKING_URI
        ),
    )


def _required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement manquante : {name} (voir .env.example)"
        )
    return value
