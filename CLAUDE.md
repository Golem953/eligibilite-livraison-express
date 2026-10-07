# CLAUDE.md

Contexte du projet **eligibilite-livraison-express** : prédiction de l'éligibilité d'une commande à la livraison express. Projet de M2 (industrialisation IA), architecture hexagonale.

## Stack

Python 3.14, pandas, scikit-learn, joblib, MLflow, FastAPI/uvicorn. Tests avec pytest, lint avec ruff. Docker + docker-compose, CI/CD GitHub Actions prévue plus tard (dossier `.github/workflows/` vide pour l'instant : un fichier `.yml` vide y fait échouer Actions).
Le notebook d'exploration (`../project_test_v1_final_final2.ipynb`) génère des commandes synthétiques et écrit ses prédictions batch dans un CSV.

## Architecture (hexagonale)

```
src/
├── domain/            # entities/, custom_execption/  (métier pur, aucune dépendance technique)
├── application/       # services/  (use cases)
└── infrastructure/
    ├── adapter/       # http/controller/, dependency_injection/
    ├── repository/    # adapters de persistance
    ├── ml/
    └── logger/
```

Conventions retenues pendant les discussions :

- **Ports = contrats** (classes `ABC` ne contenant que des `@abstractmethod`, ou `typing.Protocol`). Les adapters les implémentent, et les routes ne dépendent que du port, injecté via `Depends` de FastAPI.
- **Port in (inbound)** : ce que l'app expose (use cases). **Port out (outbound)** : ce dont l'app a besoin (BDD, stockage de modèle). Ne pas nommer un dossier `in/`, car `in` est un mot réservé Python : utiliser `inbound/` et `outbound/`.
- **Nommage** : pas de « abstract » dans les noms. **Toute interface (ports dans `application/port/`, interfaces techniques dans `infrastructure/interface/`) porte le suffixe `Interface`**, dans le nom de classe et de fichier (`OrderRepositoryInterface` dans `order_repository_interface.py`). Les implémentations n'ont pas ce suffixe et sont préfixées par la techno (`SqlOrderRepository`, `SqliteConnector`).
- Préférer des ports **par entité métier** avec des méthodes métier, plutôt qu'un `DatabaseInterface` générique exposant `execute(sql)`.
- **Toute valeur choisie par un humain** (règles qualité du nettoyage et de la validation, variables du modèle, découpage train/test, hyperparamètres, scores évalués, seuil de décision, règle du champion) va dans `infrastructure/config/training.toml` (chargé par `training_config.py`), jamais en dur dans le code.
- **Code repris du notebook** : copié tel quel autant que possible. Outils de données dans `infrastructure/ml/transform/` (`CleanDataset`, `ValidateDataset`, `OrdersToDataframe` : classe + méthode), pipeline dans `ml/model_pipeline.py`, entraînement global dans `ml/sklearn_model_trainer.py`.
- Le choix de l'adapter se fait à un seul endroit (composition root / `dependency_injection`), selon la config. Les variables d'environnement (`.env`) ne sont lues que dans `infrastructure/config/settings.py` (`get_settings()`). La composition root garde le câblage en Python (ex. `_REPOSITORY_FACTORIES` : préfixe de `DATABASE_URL` → fabrique), pas dans un fichier de config.
- **Persistance en deux étages** : les services dépendent du port `OrderRepositoryInterface` (`application/port/outbound/order_repository_interface.py`), implémenté par `SqlOrderRepository` (SQL standard, commun à tous les moteurs). Ce repository reçoit un `DatabaseConnectorInterface` (`infrastructure/interface/database_connector_interface.py`), interface **technique** implémentée par `SqliteConnector` et `PostgresConnector`. Le `DatabaseConnectorInterface` n'est pas un port : aucun service ne l'utilise. Changer de moteur = changer `DATABASE_URL` ; `container.py` choisit le repository selon le préfixe de l'URL (`_REPOSITORY_FACTORIES`). Nouveau moteur SQL (MariaDB…) = un connecteur + un script de schéma ; moteur non SQL (MongoDB…) = une nouvelle implémentation de `OrderRepositoryInterface`.

## Décisions d'architecture

Toutes les ADR sont dans [ADR.md](ADR.md). **Ne rien trancher sans validation de l'utilisateur** : il veut réfléchir avant chaque décision.

### ADR-0001 : stockage des commandes (Accepté)

- Les commandes à stocker sont les **nouvelles commandes reçues par l'API**. Elles sont prédites, stockées, puis servent au **réentraînement**.
- Flux envisagé pour `POST /predict` : INSERT de la commande (statut « reçue ») → appel du modèle → UPDATE avec prediction, probabilité, version du modèle (statut « prédite ») → réponse.
- Point important : **la prédiction n'est pas un label**. Réentraîner sur ses propres prédictions crée une boucle de rétroaction. Il faut remonter le **résultat réel** plus tard (statut « labellisée »), et le réentraînement ne lit que les lignes où `label_reel IS NOT NULL`. Une commande **labellisée sans prédiction** est autorisée : c'est une commande historique, antérieure au modèle (données d'amorçage générées par `tools/generate_orders.py`, qui demande au lancement s'il faut vider la base ou ajouter aux données existantes).
- **Décision : SQLite en dev** (léger, instantané, pour les futurs collaborateurs), **PostgreSQL en CI et en prod**. Le moteur est choisi par `DATABASE_URL`. Docker : `docker compose --env-file .env.dev up -d --build` (ou `.env.prod`). `DATABASE=sqlite|postgresql` active via `COMPOSE_PROFILES` le service `db` uniquement pour postgresql ; `DATABASE_URL` est passé à l'API. Modèle : `.env.example`. **Ne jamais lire `.env.dev` ni `.env.prod` : demander à l'utilisateur.** Ports publiés : API 8057, PostgreSQL 8058.
- **Le code doit être agnostique du moteur** : aucune fonctionnalité propre à un SGBD (pas de `JSONB`, etc.). Les contrôles sont portés par le schéma (contraintes explicites) et par la validation côté code. La CI exécute les tests du repository sur SQLite **et** PostgreSQL.
- **SQLite doit être strict au maximum** : `PRAGMA foreign_keys = ON` à chaque connexion, toutes les tables en `STRICT` (pas de type `ANY`), longueurs, booléens, dates et statuts contrôlés par des `CHECK`. Des tests vérifient que les données invalides sont rejetées sur les deux moteurs. Détail dans l'ADR-0001. Outil de consultation des données : DBeaver.
- **Accès SQL : pilotes natifs** (`sqlite3`, `psycopg`), pas d'ORM ni d'Alembic. Un script de schéma par moteur dans `infrastructure/repository/schema/` (`sqlite.sql`, `postgres.sql`), avec les mêmes contraintes.
- Encore ouverts : comment remonte le label réel (route API, import batch, simulation) ? Quel volume viser ? Évolution du schéma (migrations) quand il changera.

### ADR-0002 : stockage des artéfacts du modèle (Accepté)

- **Décision : MLflow Tracking + Model Registry** (serveur MLflow en conteneur). Raisons : simplicité d'utilisation, métriques utilisées pour la prod, visibilité sur la version qui tourne, envie d'apprendre MLflow.
- Chaque entraînement est un run MLflow. Le modèle est inscrit au registre, et la version en prod est désignée par un alias. La version stockée avec chaque prédiction (ADR-0001) est celle du registre.
- L'API charge le modèle une seule fois au démarrage. Accès via le port `outbound/model_repository_interface.py`, adapter `MlflowModelRepository`.
- **Backend store MLflow : base dédiée, séparée de celle des commandes.** Dev : deux fichiers SQLite (`commandes.db`, `mlflow.db`). CI/Prod : un seul conteneur PostgreSQL avec deux bases (`commandes`, `mlflow`). Les règles STRICT de l'ADR-0001 ne s'appliquent pas aux tables de MLflow.
- **Artifact store : volume Docker** monté sur le conteneur MLflow (seul MLflow le monte, l'API et l'outil d'entraînement passent par l'API HTTP). **Un utilisateur PostgreSQL par base** : `commandes_user` (API, outil d'entraînement), `mlflow_user` (serveur MLflow).
- **Implémenté** : service `mlflow` dans docker compose (image `ghcr.io/mlflow/mlflow:v3.17.0`, `--allowed-hosts` obligatoire, interface sur 8059), backend store SQLite dans le volume `mlflow_data` en attendant PostgreSQL (`MLFLOW_BACKEND_STORE_URI`). L'API reçoit `MLFLOW_TRACKING_URI=http://mlflow:5000` ; hors Docker, défaut `sqlite:///data/mlflow.db`. Modèles au format skops (`skops_trusted_types`).
- **Champion automatique** : après chaque entraînement, `TrainService` donne l'alias `champion` à la nouvelle version si elle bat le champion sur `[promotion].metrics` (liste par ordre de priorité : le 1er décide, les suivants départagent ; égalité totale = champion conservé), ou s'il n'y a pas de champion. Scores calculés : `[evaluation].metrics`, choisis parmi `METRIC_FUNCTIONS` de `sklearn_model_trainer.py`.
- **Prédiction** : `POST /predict` et `POST /predict/batch` (`predict_controller.py`) → port d'entrée `PredictEligibilityInterface` (`PredictService`) → `EligibilityPredictorInterface` (`MlflowEligibilityPredictor` : charge `@champion` au 1er appel puis le garde en mémoire, 503 si absent). Prédit puis enregistre la commande au statut « prédite » en une écriture. Fonctions du notebook dans `ml/predict/eligibility_prediction.py`.
- Encore ouverts : base `mlflow` + utilisateur dans PostgreSQL, rechargement du modèle par l'API, reproductibilité des données, exposition de l'interface MLflow (8059 à confirmer).
- Format des ADR (modèle du cours) : Status, Date, Contexte, Options (tableau Avantage / Inconvénient), Décision, Conséquences.

### ADR-0003 : exécution de l'entraînement (Accepté)

- **Décision : outil en ligne de commande, dans le même dépôt que l'API, exécuté dans un processus séparé.** Même `src/` (domaine, ports, repositories partagés), deux points d'entrée : API (service permanent, adapter HTTP) et CLI (lancé, travaille, s'arrête, adapter `infrastructure/adapter/cli/`). L'API n'importe jamais le code d'entraînement, et la CLI n'importe jamais FastAPI.
- Le notebook (`../project_test_v1_final_final2.ipynb`) contient tout le ML actuel : son code utile migre vers `src/`. La génération de données fictives va dans les fixtures de test ou un script de seed. La préparation des variables est intégrée au Pipeline sklearn.
- Il n'existe **pas de conteneur `training`** : l'ancienne proposition « api / training / stockage » est remplacée par cette décision.
- **Route `POST /train`** (`infrastructure/adapter/http/controller/train_controller.py`) : lance la CLI d'entraînement dans un processus séparé via `TrainingLauncherInterface` / `SubprocessTrainingLauncher`, répond 202 (409 si un entraînement tourne déjà). Chaîne : `TrainService` (application) → `OrderRepositoryInterface.find_labelled`, `ModelTrainerInterface` (`SklearnModelTrainer`, pipeline du notebook), `ModelRepositoryInterface` (`MlflowModelRepository`, version au registre `eligibilite-express`). Point d'entrée API : `src/main.py`.
- Encore ouverts : déclenchement automatique (cron, condition, dégradation, CI), image unique à confirmer, authentification de `/train`, promotion et rechargement du modèle.
