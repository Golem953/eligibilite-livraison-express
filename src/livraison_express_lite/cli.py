"""Interface en ligne de commande : le point d'entrée non HTTP.

```bash
python -m livraison_express serve                      # démarre l'API
python -m livraison_express train                      # entraîne et sauvegarde le modèle
python -m livraison_express predict --file order.json  # prédiction en local, sans serveur
```

Pourquoi une CLI en plus de l'API ? Parce que toutes les opérations d'un projet ML ne
sont pas des requêtes HTTP : l'entraînement est ici un **job** (CI, cron),
pas un endpoint. Exposer un `POST /train` serait une erreur d'architecture :
n'importe qui pourrait consommer le CPU/GPU du service de prédiction.

Code de sortie : `0` = succès, `1` = échec. Un job en CI qui renvoie 0 après un
entraînement raté est un piège silencieux, d'où le `try/except` central de `main()`
qui journalise l'erreur complète et renvoie 1 (la trace part dans stderr, pas dans
un faux succès).
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
import sys
import time
import traceback
from pathlib import Path

from src.livraison_express_lite.domain.entities import OrderEntity
from src.livraison_express_lite.core.learning.ml_trainer import MLTrainer
from src.livraison_express_lite.infrastructure.order_repository import OrderRepository

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """On construit les arguments de la ligne de commande (`serve`, `train`, `predict`)."""
    parser = argparse.ArgumentParser(
        prog="livraison_express",
        description="Outils du projet eligibilite-livraison-express.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    serve = subcommands.add_parser("serve", help="Démarrer l'API de prédiction.")
    serve.add_argument("--host", default="127.0.0.1", help="Adresse d'écoute (défaut : %(default)s).")
    serve.add_argument("--port", type=int, default=8000, help="Port d'écoute (défaut : %(default)s).")

    subcommands.add_parser(
        "train",
        help="Entraîner le modèle et écrire ses artefacts (MODEL_PATH).",
    )

    predict = subcommands.add_parser(
        "predict",
        help="Prédire l'éligibilité d'une commande lue dans un fichier JSON.",
    )
    predict.add_argument(
        "--file",
        required=True,
        help="Fichier JSON contenant une commande (champs du schéma OrderFeatures).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """On renvoie les arguments de la ligne de commande vers les fonctions Python associées
    et on retourne un code (succès = 0, échec = 1).
    """
    args = build_parser().parse_args(argv)
    try:
        if args.command == "serve":
            return _serve(args)
        if args.command == "train":
            return _train()
        if args.command == "predict":
            return _predict(args.file)
    except KeyboardInterrupt:
        print("Interrompu.", file=sys.stderr)
        return 1
    except Exception:  # fin du processus : trace complète sur stderr, exit 1
        traceback.print_exc()
        return 1
    return 1  # Si aucune condition n'est réunie, on retourne un échec.


def _serve(args: argparse.Namespace) -> int:
    """On lance l'API sur le port 8000 par défaut."""
    import uvicorn

    from .api.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def _train() -> int:
    """Entrainement du modèle de machine learning."""
    from .core.core import Core

    started_at = time.perf_counter()
    core = Core()
    logger.info("Début de l'entraînement du modèle")
    core.train_model()
    logger.info("Entraînement terminé avec succès en %.2f s", time.perf_counter() - started_at)
    return 0


def _predict(file_path: str) -> int:
    """Charger le modèle persisté puis prédire une commande JSON."""
    from .core.core import Core

    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    order = OrderEntity(**payload)
    core = Core(load_model=True)
    predict_service = core.get_predict_service()

    if predict_service is None:
        print(
            f"Modèle indisponible ({core.get_settings().model_path}) : "
            "lancez `python -m livraison_express train` d'abord.",
            file=sys.stderr,
        )
        return 1

    prediction = predict_service.predict(order)
    print(json.dumps(asdict(prediction), ensure_ascii=False, indent=2))
    return 0
