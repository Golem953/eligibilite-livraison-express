"""Vérifie que le DAG de réentraînement se charge dans Airflow (ADR-0011).

Lancé par la CI dans l'image Airflow du projet (airflow/Dockerfile), celle de la prod :

    docker run --rm -v ./airflow:/opt/airflow/check:ro <image> python /opt/airflow/check/check_dag.py

Airflow analyse le dossier des DAG comme en prod : une erreur d'import, une tâche
manquante ou un enchaînement modifié fait échouer la vérification. Aucune base ni
aucun service n'est nécessaire.
"""

from __future__ import annotations

import os
import sys

# Valeurs factices : le DAG les exige au chargement, mais ne s'y connecte pas.
os.environ.setdefault("RETRAIN_APP_IMAGE", "ghcr.io/exemple/livraison-express:0.0.0")
os.environ.setdefault("RETRAIN_TRAINING_SOURCE_URL", "mongodb://exemple:27017/livraison_express")

from airflow.dag_processing.dagbag import DagBag  # noqa: E402

DAG_FOLDER = os.environ.get("DAG_FOLDER", "/opt/airflow/check/dags")
DAG_ID = "retrain_express_model"
# Chaque tâche et celles qu'elle déclenche directement.
EXPECTED = {
    "enough_new_orders": {"train"},
    "train": {"read_result"},
    "read_result": {"remember_order_count", "model_promoted"},
    "remember_order_count": set(),
    "model_promoted": {"restart_api"},
    "restart_api": set(),
}

bag = DagBag(dag_folder=DAG_FOLDER)
errors = [f"Erreur d'import dans {path} :\n{error}" for path, error in bag.import_errors.items()]
dag = bag.dags.get(DAG_ID)
if dag is None:
    errors.append(f"DAG {DAG_ID} introuvable dans {DAG_FOLDER}")
else:
    actual = {task.task_id: set(task.downstream_task_ids) for task in dag.tasks}
    if actual != EXPECTED:
        errors.append(
            f"Tâches ou enchaînement inattendus :\n  attendu {EXPECTED}\n  obtenu  {actual}"
        )

if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print(f"DAG {DAG_ID} chargé : {len(dag.tasks)} tâches, enchaînement conforme.")
