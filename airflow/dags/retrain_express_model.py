"""Réentraînement nocturne du modèle d'éligibilité express (ADR-0010).

Chaque nuit :

1. ``enough_new_orders`` compte les commandes labellisées du MongoDB de l'ERP. S'il en
   est arrivé moins de ``RETRAIN_MIN_NEW_ORDERS`` depuis le dernier entraînement, le
   DAG s'arrête là : les tâches suivantes sont sautées ;
2. ``train`` lance l'image de prod de l'application (``python -m app train``) dans un
   conteneur, sur le volume du modèle de la prod. L'application compare elle-même le
   nouveau modèle au modèle en service, sur le même jeu de test, et ne remplace ce
   dernier que si le nouveau est meilleur (ADR-0009) ;
3. ``read_result`` lit le résultat, écrit en JSON sur la dernière ligne de ``train`` ;
4. ``remember_order_count`` retient le nombre de commandes utilisées, pour le seuil de
   la nuit suivante, que le modèle ait été promu ou non ;
5. ``restart_api`` redémarre l'API de prod, seulement si le modèle a changé : elle ne
   charge le modèle qu'au démarrage.

Toute la configuration vient des variables d'environnement ``RETRAIN_*`` des conteneurs
Airflow (voir ``.env.airflow.example``). Airflow ne parle à Docker qu'à travers un proxy
qui limite les appels autorisés (``docker-proxy`` dans ``docker-compose.airflow.yml``).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import Variable, dag, get_current_context, task
from docker.types import Mount

logger = logging.getLogger(__name__)

# Variable Airflow : nombre de commandes labellisées lors du dernier entraînement.
LAST_COUNT_VARIABLE = "retrain_last_labeled_orders"
LABEL_FIELD = "express_eligible"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variable d'environnement {name} manquante")
    return value


APP_IMAGE = _required("RETRAIN_APP_IMAGE")
TRAINING_SOURCE_URL = _required("RETRAIN_TRAINING_SOURCE_URL")
MIN_NEW_ORDERS = int(os.environ.get("RETRAIN_MIN_NEW_ORDERS", "100"))
DOCKER_URL = os.environ.get("RETRAIN_DOCKER_URL", "tcp://docker-proxy:2375")
MODEL_VOLUME = os.environ.get("RETRAIN_MODEL_VOLUME", "livraison-express-prod_app_data")
API_CONTAINER = os.environ.get("RETRAIN_API_CONTAINER", "livraison-express-prod-api-1")


@dag(
    schedule=os.environ.get("RETRAIN_SCHEDULE", "0 2 * * *"),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["livraison-express", "ml"],
)
def retrain_express_model():
    @task.short_circuit
    def enough_new_orders() -> bool:
        from pymongo import MongoClient

        with MongoClient(TRAINING_SOURCE_URL, serverSelectionTimeoutMS=10_000) as client:
            collection = client.get_default_database()["orders"]
            count = collection.count_documents({LABEL_FIELD: {"$in": [0, 1]}})
        last = int(Variable.get(LAST_COUNT_VARIABLE, default="0"))
        get_current_context()["ti"].xcom_push(key="labeled_orders", value=count)
        logger.info(
            "Commandes labellisées : %d (dernier entraînement : %d, seuil : %d nouvelles)",
            count,
            last,
            MIN_NEW_ORDERS,
        )
        return count - last >= MIN_NEW_ORDERS

    train = DockerOperator(
        task_id="train",
        image=APP_IMAGE,
        command=["python", "-m", "app", "train"],
        docker_url=DOCKER_URL,
        # Mêmes réglages que le service `train` de docker-compose.prod.yml.
        environment={
            "MODEL_PATH": "/data/artifacts/express_delivery_model.joblib",
            "MLFLOW_TRACKING_URI": "/data/mlruns",
            "MLFLOW_ALLOW_FILE_STORE": "true",
            "HOME": "/tmp",
            "LOG_LEVEL": os.environ.get("RETRAIN_LOG_LEVEL", "INFO"),
            "PROMOTION_METRIC": os.environ.get("RETRAIN_PROMOTION_METRIC", "f1_score"),
            "PROMOTION_MIN_GAIN": os.environ.get("RETRAIN_PROMOTION_MIN_GAIN", "0.0"),
        },
        # Contient le mot de passe de l'ERP : jamais affiché dans les logs ni l'interface.
        private_environment={"TRAINING_SOURCE_URL": TRAINING_SOURCE_URL},
        mounts=[Mount(source=MODEL_VOLUME, target="/data", type="volume")],
        user="1000:1000",
        extra_hosts={"host.docker.internal": "host-gateway"},
        # Airflow tourne lui-même dans un conteneur : son dossier temporaire n'existe pas
        # sur la machine, il ne peut pas être monté dans le conteneur d'entraînement.
        mount_tmp_dir=False,
        auto_remove="success",
        xcom_all=True,
    )

    @task
    def read_result(lines: list[str]) -> dict:
        """Cherche, en partant de la fin, la ligne JSON écrite par `python -m app train`."""
        for line in reversed(lines or []):
            if line.lstrip().startswith('{"run_id"'):
                result = json.loads(line)
                logger.info(
                    "Run %s : promu=%s, nouveau=%s, en service=%s",
                    result["run_id"],
                    result["promoted"],
                    result["metrics"],
                    result["champion_metrics"],
                )
                return result
        raise ValueError("Résultat de l'entraînement introuvable dans la sortie de `train`")

    @task
    def remember_order_count() -> None:
        count = get_current_context()["ti"].xcom_pull(
            task_ids="enough_new_orders", key="labeled_orders"
        )
        Variable.set(LAST_COUNT_VARIABLE, str(count))

    @task.short_circuit
    def model_promoted(result: dict) -> bool:
        return result["promoted"]

    @task
    def restart_api() -> None:
        import docker

        client = docker.DockerClient(base_url=DOCKER_URL)
        client.containers.get(API_CONTAINER).restart(timeout=30)
        logger.info("API redémarrée (%s) : elle sert le nouveau modèle", API_CONTAINER)

    result = read_result(train.output)
    enough_new_orders() >> train
    result >> remember_order_count()
    model_promoted(result) >> restart_api()


retrain_express_model()
