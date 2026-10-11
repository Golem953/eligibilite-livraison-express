"""Entraîne le modèle sur toutes les commandes labellisées de la base.

Usage, depuis la racine du projet :
    python tools/train.py              # base de APP_ENV (.env), dev par défaut
    python tools/train.py --env prod   # base PostgreSQL de prod

Le modèle est suivi dans MLflow, inscrit au registre et reçoit l'alias servi par
l'API. L'API charge ce modèle à son démarrage : la redémarrer pour qu'elle serve
la nouvelle version.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
# Console Windows : un caractère non affichable (emoji des logs MLflow) est
# remplacé au lieu d'arrêter le script.
sys.stdout.reconfigure(errors="replace")
# Message d'aide que MLflow affiche à chaque import.
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

from config.environment import load_environment  # noqa: E402
from domain.ml_feature import CATEGORICAL_FEATURES, NUMERIC_FEATURES  # noqa: E402
from infrastructure.database.database import Database  # noqa: E402
from infrastructure.database.order_repository import OrderRepository  # noqa: E402
from infrastructure.ml.data_splitter import DataSplitter  # noqa: E402
from infrastructure.ml.ml_pipeline import MLPipeline  # noqa: E402
from infrastructure.ml.ml_trainer import MLTrainer  # noqa: E402
from infrastructure.ml.model_registry import ModelRegistry  # noqa: E402
from infrastructure.ml.train_test_splitter import TrainTestSplitter  # noqa: E402
from infrastructure.nettoyage.clean import Clean  # noqa: E402
from infrastructure.validation.validator import Validator  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        help="Base à lire (défaut : APP_ENV du fichier .env)",
    )
    args = parser.parse_args()

    environment = load_environment(args.env)
    print(f"Environnement : {environment.app_env}")

    database = Database(environment.database_url)
    database.create_tables()
    orders = OrderRepository(database).load_training_data()
    if orders.empty:
        sys.exit(
            "Aucune commande labellisée dans la base : "
            "lancer d'abord tools/generate_orders.py"
        )
    print(f"Commandes labellisées lues : {len(orders)}")

    # Même enchaînement que le notebook (cellules 14 à 26).
    orders_clean = Clean.clean_orders_data(orders)
    Validator.validate_dataset(orders_clean)
    print(f"Commandes après nettoyage : {len(orders_clean)}")

    X, y = DataSplitter(orders_clean).split_data(None, None)
    X_train, X_test, y_train, y_test = TrainTestSplitter(X, y).split()

    # Le registre fixe l'adresse du serveur MLflow, avant que MLTrainer s'y connecte.
    registry = ModelRegistry(environment.mlflow_tracking_uri)
    model_pipeline = MLPipeline(NUMERIC_FEATURES, CATEGORICAL_FEATURES).build_model()
    run_id = MLTrainer(model_pipeline).train(X_train, y_train, X_test, y_test)

    version = registry.register(run_id)
    print(f"Run MLflow : {run_id}")
    print(f"Modèle inscrit : {registry.model_name} version {version} "
          f"(alias {registry.alias})")


if __name__ == "__main__":
    main()
