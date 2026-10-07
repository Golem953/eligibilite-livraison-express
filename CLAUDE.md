# CLAUDE.md

Contexte du projet **eligibilite-livraison-express** : prédiction de l'éligibilité d'une commande à la livraison express. Projet de M2 (industrialisation IA), architecture hexagonale.

## Stack

Python 3.11, pandas, scikit-learn, joblib, MLflow, FastAPI/uvicorn. Tests avec pytest, lint avec ruff. Docker + docker-compose, CI/CD GitHub Actions (`.github/workflows/pipeline_ci_cd.yml`).
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
- Le choix de l'adapter se fait à un seul endroit (composition root / `dependency_injection`), selon la config. Les variables d'environnement (`.env`) ne sont lues que dans `infrastructure/config/settings.py` (`get_settings()`). La composition root garde le câblage en Python (ex. `_REPOSITORY_FACTORIES` : préfixe de `DATABASE_URL` → fabrique), pas dans un fichier de config.
- **Persistance en deux étages** : les services dépendent du port `OrderRepositoryInterface` (`application/port/outbound/order_repository_interface.py`), implémenté par `SqlOrderRepository` (SQL standard, commun à tous les moteurs). Ce repository reçoit un `DatabaseConnectorInterface` (`infrastructure/interface/database_connector_interface.py`), interface **technique** implémentée par `SqliteConnector` et `PostgresConnector`. Le `DatabaseConnectorInterface` n'est pas un port : aucun service ne l'utilise. Changer de moteur = changer `DATABASE_URL` dans le `.env` ; `container.py` choisit le repository selon le préfixe de l'URL (`_REPOSITORY_FACTORIES`). Nouveau moteur SQL (MariaDB…) = un connecteur + un script de schéma ; moteur non SQL (MongoDB…) = une nouvelle implémentation de `OrderRepositoryInterface`.

## Décisions d'architecture

Toutes les ADR sont dans [ADR.md](ADR.md). **Ne rien trancher sans validation de l'utilisateur** : il veut réfléchir avant chaque décision.

### ADR-0001 : stockage des commandes (Accepté)

- Les commandes à stocker sont les **nouvelles commandes reçues par l'API**. Elles sont prédites, stockées, puis servent au **réentraînement**.
- Flux envisagé pour `POST /predict` : INSERT de la commande (statut « reçue ») → appel du modèle → UPDATE avec prediction, probabilité, version du modèle (statut « prédite ») → réponse.
- Point important : **la prédiction n'est pas un label**. Réentraîner sur ses propres prédictions crée une boucle de rétroaction. Il faut remonter le **résultat réel** plus tard (statut « labellisée »), et le réentraînement ne lit que les lignes où `label_reel IS NOT NULL`. Une commande **labellisée sans prédiction** est autorisée : c'est une commande historique, antérieure au modèle (données d'amorçage générées par `tools/generate_orders.py`, qui demande au lancement s'il faut vider la base ou ajouter aux données existantes).
- **Décision : SQLite en dev** (léger, instantané, pour les futurs collaborateurs), **PostgreSQL en CI et en prod**. Le moteur est choisi par la config (URL de connexion).
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
- Encore ouverts : artifact store en dev (dossier local ?), promotion auto ou manuelle, rechargement du modèle par l'API, reproductibilité des données, exposition de l'interface MLflow.
- Format des ADR (modèle du cours) : Status, Date, Contexte, Options (tableau Avantage / Inconvénient), Décision, Conséquences.

### ADR-0003 : exécution de l'entraînement (Accepté)

- **Décision : outil en ligne de commande, dans le même dépôt que l'API, exécuté dans un processus séparé.** Même `src/` (domaine, ports, repositories partagés), deux points d'entrée : API (service permanent, adapter HTTP) et CLI (lancé, travaille, s'arrête, adapter `infrastructure/adapter/cli/`). L'API n'importe jamais le code d'entraînement, et la CLI n'importe jamais FastAPI.
- Le notebook (`../project_test_v1_final_final2.ipynb`) contient tout le ML actuel : son code utile migre vers `src/`. La génération de données fictives va dans les fixtures de test ou un script de seed. La préparation des variables est intégrée au Pipeline sklearn.
- Il n'existe **pas de conteneur `training`** : l'ancienne proposition « api / training / stockage » est remplacée par cette décision.
- Encore ouverts : déclenchement (manuel, cron, condition, dégradation, CI), une ou deux images Docker, promotion et rechargement du modèle, structure détaillée de `src/`.
