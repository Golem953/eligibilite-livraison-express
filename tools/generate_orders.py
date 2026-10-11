"""Remplit la base de l'API avec des commandes fictives labellisées.

Usage, depuis la racine du projet :
    python tools/generate_orders.py                 # 6000 commandes, base de APP_ENV
    python tools/generate_orders.py --rows 500 --seed 42
    python tools/generate_orders.py --env prod

Les commandes viennent de la fonction de génération du notebook (cellule 8). Elles
portent leur résultat réel (express_eligible) et servent donc à l'entraînement.
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
from infrastructure.database.database import Database  # noqa: E402
from infrastructure.database.order_repository import OrderRepository  # noqa: E402
from infrastructure.generation.order_generator import OrderGenerator  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=6000, help="Nombre de commandes")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Graine aléatoire, pour regénérer les mêmes données (défaut : aléatoire)",
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        help="Base à remplir (défaut : APP_ENV du fichier .env, comme l'API)",
    )
    args = parser.parse_args()

    environment = load_environment(args.env)
    print(f"Environnement : {environment.app_env}")

    database = Database(environment.database_url)
    database.create_tables()
    repository = OrderRepository(database)

    orders = OrderGenerator.generate_orders_dataset(
        n_rows=args.rows, random_state=args.seed
    )
    inserted = repository.add_generated_orders(orders)

    print(f"Commandes ajoutées : {inserted}")
    print(f"Commandes dans la base : {repository.count_orders()}")


if __name__ == "__main__":
    main()
