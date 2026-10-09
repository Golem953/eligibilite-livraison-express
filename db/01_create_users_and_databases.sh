#!/bin/sh
# Exécuté par l'image postgres au premier démarrage uniquement (volume vide).
# Un utilisateur par base, propriétaire de sa base (ADR-0002) :
#   commandes_user → base commandes (API, outil d'entraînement)
#   mlflow_user    → base mlflow    (serveur MLflow)
# Les tables sont créées par l'application (db/migrations), pas ici.
set -e

: "${COMMANDES_DB_PASSWORD:?COMMANDES_DB_PASSWORD doit être défini}"
: "${MLFLOW_DB_PASSWORD:?MLFLOW_DB_PASSWORD doit être défini}"

# Les mots de passe passent par des variables psql (:'nom'), qui les échappent.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v commandes_password="$COMMANDES_DB_PASSWORD" \
    -v mlflow_password="$MLFLOW_DB_PASSWORD" <<'EOSQL'
CREATE ROLE commandes_user LOGIN PASSWORD :'commandes_password';
CREATE DATABASE commandes OWNER commandes_user;
REVOKE ALL ON DATABASE commandes FROM PUBLIC;

CREATE ROLE mlflow_user LOGIN PASSWORD :'mlflow_password';
CREATE DATABASE mlflow OWNER mlflow_user;
REVOKE ALL ON DATABASE mlflow FROM PUBLIC;
EOSQL
