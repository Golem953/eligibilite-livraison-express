# Architecture Decision Records

## ADR-0001 — Où stocker les commandes reçues par l'API

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

L'API expose `POST /predict` : elle reçoit une commande, renvoie une prédiction, et **n'enregistre rien**. Ni la commande ni la prédiction ne sont conservées.

Le seul stockage de commandes est `InMemoryOrderRepository`, un dictionnaire Python rempli au démarrage par le générateur de données synthétiques (`generated=True`). La commande `train` s'entraîne sur ces données générées. Elles disparaissent à l'arrêt du processus et ne sont pas partagées entre l'API et `train`, qui tournent dans deux processus distincts.

L'abstraction `OrderRepository` existe déjà (`save`, `get`, `get_all`, `count`), mais l'implémentation est choisie en dur dans `core/core.py`. `config.py` déclare `ORDER_REPOSITORY_URL` (valeur par défaut `memory://`) sans s'en servir.

Ce que le stockage doit permettre :

- **Écrire une ligne à chaque appel de l'API.** Les écritures sont fréquentes et unitaires. Elles peuvent être concurrentes si l'API tourne avec plusieurs workers.
- **Conserver la prédiction et la version du modèle** qui l'a produite (`PredictionEntity.model_version`), pour l'audit et le monitoring.
- **Compléter la commande plus tard avec le résultat réel** (la livraison express était-elle vraiment possible ?). Sans ce label, la commande ne sert pas au réentraînement. Il faut donc pouvoir **mettre à jour** ou **joindre** des données après coup.
- **Extraire un jeu d'entraînement** (commandes labellisées sur une période donnée) que l'entraînement charge dans pandas via `orders_to_dataframe()`.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. SQLite | Un seul fichier, SQL disponible, aucun service | Un seul écrivain à la fois. Inutilisable si l'API et l'entraînement tournent sur deux machines |
| B. PostgreSQL (conteneur docker-compose) | Écritures concurrentes, mises à jour et jointures faciles, standard en production, type `JSONB`. Bon support comme backend MLflow (base mutualisable avec l'ADR-0002) | Service supplémentaire à maintenir (configuration, sauvegardes, migrations) |
| C. MariaDB (conteneur docker-compose) | Écritures concurrentes, mises à jour et jointures faciles, prise en main simple si l'équipe connaît MySQL | Service supplémentaire à maintenir. Support JSON moins riche que PostgreSQL. Moins courant comme backend MLflow |
| D. En mémoire en dev, PostgreSQL en CI et en prod | Dev instantané : aucun service, aucun fichier, aucun Docker. `InMemoryOrderRepository` existe déjà. Robustesse de PostgreSQL là où ça compte | En dev, les données disparaissent à chaque redémarrage et ne sont pas partagées entre processus. Aucune contrainte de base en dev : certaines erreurs de données n'apparaissent qu'en CI |

### Décision

**Option D : stockage en mémoire en développement, PostgreSQL en test (CI) et en production.**

- **En dev, en mémoire** (`InMemoryOrderRepository`) : rien à installer, démarrage instantané. L'objectif est l'environnement de développement le plus rapide possible pour les futurs collaborateurs.
- **En CI et en prod, PostgreSQL** : persistance, écritures concurrentes, données partagées entre l'API et l'entraînement, typage strict.
- **En contrepartie de l'absence de contraintes en mémoire**, la CI exécute les mêmes tests sur les deux implémentations, et les données sont validées avant d'atteindre le repository.
- **Le métier ne dépend pas du moteur** : l'API, l'entraînement et le domaine ne connaissent que l'abstraction `OrderRepository`. Seule l'implémentation PostgreSQL contient du SQL.

#### Durée de vie des données en mémoire

Les commandes et les prédictions sont stockées dans un dictionnaire Python, à l'intérieur du **processus** de l'API, pas dans le conteneur ni sur le disque :

| Situation | Données conservées ? |
|---|---|
| L'API tourne et reçoit des requêtes | Oui |
| Redémarrage du processus : arrêt ou redémarrage du conteneur, redéploiement, plantage, rechargement automatique (`--reload`) | **Non**, tout est perdu |
| Lecture depuis un autre processus (commande `train`, deuxième API) | **Non**, chaque processus a son propre dictionnaire |
| API lancée avec plusieurs workers uvicorn | **Partiellement** : chaque worker a son propre dictionnaire, donc les commandes sont réparties entre eux |

C'est acceptable en dev, car les données sont synthétiques et regénérées au démarrage (`generated=True`). C'est inacceptable en prod, d'où PostgreSQL.

### Conséquences

- **Choix de l'implémentation par configuration** : `Settings.order_repository_url` (`ORDER_REPOSITORY_URL`) détermine l'implémentation : `memory://` (valeur par défaut) ou `postgresql://…`. Ce choix se fait uniquement dans la racine de composition `core/core.py`, qui instancie aujourd'hui `InMemoryOrderRepository` en dur. Il faut la remplacer par une factory qui lit l'URL.
- **Incohérence de configuration à corriger** : `.env.example` documente `ORDER_STORE_DSN` alors que `config.py` lit `ORDER_REPOSITORY_URL`. Il faut aligner les deux sur `ORDER_REPOSITORY_URL`.
- **Contrat du repository à compléter** : `get_training_data()` est utilisé par `Core.train_model()` mais n'existe que dans `InMemoryOrderRepository`. Il faut l'ajouter à `OrderRepository`, avec des méthodes pour enregistrer une prédiction et pour poser le label réel.
- **Identifiant obligatoire à l'enregistrement** : `order_id` est facultatif dans `OrderEntity`, et `InMemoryOrderRepository.save()` range la commande sous la clé `order_id`. Toutes les commandes sans identifiant écrasent donc la même entrée (`None`). L'API doit générer un identifiant avant d'enregistrer, ou le repository doit refuser une commande sans identifiant.
- **Cycle complet testé uniquement avec PostgreSQL** : en dev, `train` s'entraîne sur les données générées, jamais sur les prédictions reçues par l'API. La chaîne prédiction → label réel → réentraînement ne se vérifie qu'avec PostgreSQL, en CI ou avec `docker compose` (ADR-0004).
- **Un seul worker en dev** : l'API en mémoire tourne avec un seul worker uvicorn (déjà le cas avec `serve`), pour que toutes les requêtes voient les mêmes données.
- **Contrôles portés par le code et le schéma, pas par le stockage en mémoire** : le dictionnaire accepte n'importe quelle valeur. Les données sont donc validées par l'API (ADR-0007) avant l'écriture, et le schéma PostgreSQL déclare explicitement ses contraintes (`NOT NULL`, `CHECK` sur les bornes et les valeurs énumérées, `UNIQUE` sur `order_id`, clés étrangères entre commandes et prédictions).
- **Tests de contrat en CI** : une même suite de tests vérifie les deux implémentations (`InMemoryOrderRepository` et l'implémentation PostgreSQL, via un service container GitHub Actions). Elle couvre l'absence de doublon sur `order_id`, `get` qui renvoie `None` pour un identifiant inconnu, et le rejet des données invalides. Un test qui passe sur l'une et échoue sur l'autre bloque le pipeline.
- **Outillage SQL et migrations** : SQLAlchemy et Alembic (déjà dans `requirements.txt`) pour l'implémentation PostgreSQL.
- **Déploiement** : un serveur PostgreSQL fonctionne, que l'API et l'entraînement tournent sur une ou deux machines.
- **Outillage** : DBeaver pour consulter la base PostgreSQL.
- **Architecture** : l'accès aux commandes passe par l'abstraction `infrastructure/order_repository.py`. L'implémentation PostgreSQL va dans `infrastructure/implementation/` (par exemple `sql/sql_order_repository.py`). Passer de la mémoire à PostgreSQL revient à changer la configuration, sans toucher au métier ni à l'API.

### Points restant ouverts (sans impact sur le choix du moteur)

- Quel **volume** de commandes viser (par jour, au total) ?
- Comment et quand le **label réel** remonte-t-il (par l'API, par un import batch, par simulation) ?
- Le **générateur de données synthétiques** remplit aujourd'hui le dépôt en mémoire au démarrage (`generated=True`). En CI et en prod, il devient un outil séparé qui alimente la base PostgreSQL de test.

---

## ADR-0002 — Où stocker les artéfacts du modèle de Machine Learning

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

La commande `train` produit le modèle (pipeline scikit-learn) et `FileModelRepository` l'écrit dans `notebooks/artifacts/` (`MODEL_PATH`), sous forme de trois fichiers : `express_delivery_model.joblib`, `metrics.json` et `features.json`. Chaque entraînement **écrase** les fichiers précédents. Ce dossier est exclu de git.

L'API charge ce fichier une seule fois, au démarrage.

La version indiquée dans chaque prédiction (`model_version`) vient de la configuration (`MODEL_VERSION=1.0.0`), et non du fichier chargé.

Ce que le stockage doit permettre :

- **Écrire une nouvelle version** du modèle à chaque entraînement, avec ses métriques et ses hyperparamètres.
- **Charger la version en production** au démarrage de l'API.
- **Tracer chaque prédiction** : la version enregistrée avec une prédiction doit permettre de retrouver le modèle exact qui l'a produite.
- **Revenir en arrière** vers une version précédente si un nouveau modèle se dégrade.
- **Suivre l'évolution** des modèles : savoir quelle version tourne et comment ses performances évoluent d'un entraînement à l'autre.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Modèle intégré à l'image Docker (`.joblib` copié au build) | Très simple : l'image et le modèle sont versionnés ensemble | Chaque réentraînement impose un rebuild et un redéploiement. Binaire dans git (ou git LFS). Aucune métrique associée |
| B. Fichiers locaux ou volume partagé (`models/<version>/model.joblib` + `metadata.json` + pointeur vers la version courante), dans la continuité de `FileModelRepository` | Aucun service supplémentaire : l'entraînement écrit, l'API lit | Versioning et métadonnées faits maison. Une seule machine. Aucune interface |
| C. MLflow Tracking + Model Registry (conteneur serveur MLflow) | Versions, métriques, paramètres et lien vers le run d'entraînement. Alias pour désigner la version en production. Interface web. Retour arrière simple. MLflow est déjà utilisé par `MLTrainer` | Un service de plus. L'API dépend du serveur MLflow au démarrage. Courbe d'apprentissage |

### Décision

**Option C : MLflow Tracking + Model Registry.**

- **Simplicité d'utilisation** : le registre et l'interface web évitent de réinventer le versioning, les métadonnées et le retour arrière.
- **Métriques au service de la production** : chaque entraînement enregistre ses métriques, qui servent à juger si une version mérite de passer en production.
- **Visibilité** : savoir à tout moment quelle version tourne et où en sont les performances.
- **Continuité** : `MLTrainer` journalise déjà ses runs dans MLflow. Il reste à configurer un serveur et à inscrire le modèle dans le registre.
- **Apprentissage** : MLflow est un outil standard du MLOps. La courbe d'apprentissage est acceptée, et même recherchée.

**Backend store de MLflow (métadonnées et Model Registry) : des fichiers locaux en dev ; en CI et en prod, une base dédiée, séparée de celle des commandes, sur le même moteur que l'ADR-0001.**

| Environnement | Base des commandes (ADR-0001) | Backend store MLflow |
|---|---|---|
| Dev | En mémoire (`InMemoryOrderRepository`) | Dossier `mlruns/` à la racine du projet (stockage fichiers de MLflow) |
| CI / Prod | Base `commandes` | Base `mlflow`, **dans le même conteneur PostgreSQL** |

- **Séparer les bases** évite que les tables de MLflow et les nôtres se mélangent (collisions de noms, table `alembic_version` partagée si nos migrations utilisent aussi Alembic). Chaque base garde ses propres migrations et sauvegardes.
- **Un seul conteneur PostgreSQL** suffit : pas de second serveur à maintenir.
- **En dev, MLflow stocke tout dans des fichiers** (dossier `mlruns/`) : runs, métriques, registre, alias et fichiers des modèles. Aucune base de données et aucun serveur ne sont nécessaires. Contrairement aux commandes, ces données ne peuvent pas être en mémoire : l'historique des runs et le registre doivent survivre d'un entraînement à l'autre.
**Artifact store (fichiers du modèle) : un volume Docker monté sur le conteneur MLflow.**

- Les fichiers des modèles (`model.pkl` ou `model.skops`, `MLmodel`, `requirements.txt`…) sont écrits dans un dossier du conteneur MLflow (par exemple `/mlflow/mlartifacts`), monté sur un volume Docker. Ils survivent à la suppression et à la recréation du conteneur.
- Le serveur MLflow sert d'intermédiaire : l'entraînement et l'API envoient et récupèrent les fichiers par son API HTTP. Seul le conteneur MLflow monte le volume.

**Droits d'accès en CI et en prod : un utilisateur PostgreSQL par base** (en dev, un seul compte administrateur, voir l'ADR-0008).

| Utilisateur | Base | Utilisé par |
|---|---|---|
| `commandes_user` | `commandes` | l'API et l'entraînement |
| `mlflow_user` | `mlflow` | le serveur MLflow uniquement |

Aucun service ne peut modifier la base d'un autre.

### Conséquences

- **Nouveau service** : un conteneur serveur MLflow s'ajoute au docker-compose (ADR-0004), aux côtés de l'API et de la base.
- **Configuration** : une variable `MLFLOW_TRACKING_URI` s'ajoute à `config.py` et à `.env.example`, et `MLTrainer` comme l'API l'appliquent avant tout appel à MLflow (`mlflow.set_tracking_uri`). En dev, sa valeur par défaut pointe vers le dossier `mlruns/` à la racine du projet, avec un chemin absolu calculé dans `config.py` pour ne pas dépendre du dossier depuis lequel la commande est lancée. En CI et en prod, elle pointe vers le serveur MLflow (`http://mlflow:5000`).
- **`.gitignore`** : `mlruns/` est exclu du dépôt.
- **Initialisation de PostgreSQL** : un script exécuté au premier démarrage du conteneur crée les deux bases (`commandes`, `mlflow`) et leurs utilisateurs, chacun propriétaire de sa seule base.
- **Secrets** : deux couples identifiant / mot de passe à fournir par variables d'environnement (`.env`, non versionné), un par base.
- **Volume des artéfacts** : lié à la machine hôte. Sa sauvegarde doit être prévue explicitement. En cas de passage à plusieurs machines, l'artifact store pourra migrer vers un stockage compatible S3 (MinIO) en changeant uniquement la configuration du serveur MLflow, sans toucher au code de l'API ni de l'entraînement.
- **Schéma géré par MLflow** : MLflow crée et fait évoluer ses propres tables (`mlflow db upgrade`). Les contraintes de l'ADR-0001 (`NOT NULL`, `CHECK`, `UNIQUE`…) s'appliquent à nos tables, pas à celles de MLflow.
- **Chaque entraînement est un run MLflow** (déjà le cas) : paramètres, métriques et modèle y sont enregistrés. Le modèle est en plus inscrit dans le Model Registry sous un nom unique (`registered_model_name`), et la version en production est désignée par un alias.
- **La version vient du registre, plus de la configuration** : `MODEL_VERSION` disparaît. `PredictionEntity.model_version` et la model card (`ModelEntity`) portent la version du Model Registry. La version stockée avec chaque prédiction (ADR-0001) correspond donc à un modèle réellement retrouvable.
- **Dépendance au démarrage** : l'API charge le modèle **une seule fois au démarrage** et le garde en mémoire (déjà le cas avec `Core(load_model=True)`). Elle ne sollicite pas MLflow à chaque prédiction.
- **Architecture** : l'accès au modèle passe par l'abstraction `infrastructure/model_repository.py`, implémentée par une nouvelle classe `MlflowModelRepository`. `FileModelRepository` reste disponible pour les tests et le dev hors ligne. Le choix se fait dans `core/core.py`, selon la configuration. L'API et le métier ne dépendent pas directement de MLflow.

### Points restant ouverts

- **Promotion en production** : automatique si le nouveau modèle fait mieux que l'actuel (champion / challenger), ou validée par un humain ?
- **Prise en compte d'un nouveau modèle par l'API** : au redémarrage, via une route de rechargement, ou par vérification périodique ?
- **Reproductibilité des données** : enregistrer dans le run la période ou une empreinte du jeu d'entraînement extrait de la base ?
- **Interface MLflow** : exposée ou non, et à qui ?

---

## ADR-0003 — Où et comment exécuter l'entraînement du modèle

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

Le code de Machine Learning du notebook (`notebooks/project_test_v1_final_final2.ipynb`) a été extrait dans `src/livraison_express_lite/core/learning/` : pipeline (`MLPipeline`), découpage (`TrainTestSplitter`), entraînement (`MLTrainer`), prédiction (`MLPredict`) et contrat des features (`order_feature.py`). Le notebook reste dans le dépôt comme trace de l'exploration.

L'entraînement doit :

- **Pouvoir lire de vraies commandes labellisées**, et pas seulement les données générées.
- **Produire une nouvelle version du modèle** à chaque exécution, sans écraser la précédente.
- **Partager le même code** que la prédiction pour la validation des commandes et la préparation des variables. Sinon, le modèle reçoit en production des données préparées différemment de celles sur lesquelles il a appris.
- **Ne pas dégrader l'API** : un entraînement est long et consomme du CPU, alors que l'API doit rester disponible et rapide.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Entraînement exécuté dans l'API (une route `POST /train` dans le processus de l'API) | Un seul programme, déclenchable par HTTP | Ralentit les prédictions pendant l'entraînement. Un plantage de l'entraînement fait tomber l'API |
| B. Commande en ligne de commande dans le même dépôt, exécutée dans un processus séparé | Code partagé avec l'API, donc toujours synchronisé. API non impactée. Déclenchable par un humain, un cron ou la CI | Un point d'entrée supplémentaire à maintenir |
| C. Projet séparé, dans un autre dépôt | Isolation totale | Code partagé dupliqué ou à publier en bibliothèque. Risque de désynchronisation entre l'entraînement et la prédiction |
| D. Entraînement manuel depuis le notebook | Rien à développer | Non reproductible, non automatisable : contraire à l'objectif d'industrialisation |

### Décision

**Option B : l'entraînement est une commande en ligne de commande (`python -m livraison_express_lite train`), dans le même dépôt que l'API, exécutée dans un processus séparé.**

- **Même dépôt, même `src/`** : l'API et l'entraînement partagent le domaine (`OrderEntity`), le contrat des features (`FEATURE_COLUMNS`) et les repositories. Une évolution du modèle (une nouvelle variable, par exemple) modifie l'entraînement et la prédiction dans le même commit.
- **Deux points d'entrée distincts** : `serve` lance un service qui tourne en permanence. `train` est lancé, fait son travail, puis s'arrête avec un code de sortie (0 = succès, 1 = échec) exploitable par un cron ou la CI.
- **Isolation** : l'API n'importe jamais le code d'entraînement, et l'entraînement n'importe jamais FastAPI.

### Conséquences

- **Isolation à corriger** : aujourd'hui, `api/app.py` importe `Core`, qui importe `MLTrainer` et donc `mlflow` et les métriques d'entraînement. `Core` doit être séparé en deux assemblages : l'un pour servir (modèle chargé + `MLPredict`), l'autre pour entraîner (`MLTrainer` + `MLPipeline`). L'API n'utilise que le premier.
- **Singleton à revoir** : `Core` est un singleton dont l'état dépend du premier appel (`load_model`). Une factory explicite par point d'entrée simplifie les tests et évite qu'une configuration fuie d'un test à l'autre (voir la section 12 de l'architecture).
- **Nom du module à aligner** : la documentation de la CLI annonce `python -m livraison_express`, alors que le package s'appelle `livraison_express_lite`. `cli.py` mélange aussi des imports absolus `src.livraison_express_lite…` et des imports relatifs. Il faut uniformiser en imports relatifs pour que le package installé fonctionne.
- **Données d'entraînement** : `train` lit les commandes labellisées dans la base (ADR-0001) et non plus le générateur en mémoire. La génération de données synthétiques devient une commande séparée qui alimente la base de dev ; elle n'est pas du code de production.
- **Préparation des variables dans le pipeline** : le nettoyage et la préparation des variables restent intégrés au pipeline scikit-learn (`MLPipeline`) enregistré dans MLflow. Cela garantit un traitement identique à l'entraînement et à la prédiction.
- **La model card est construite à partir du contrat** : `Core.train_model()` recopie aujourd'hui la liste des features en dur. Elle doit utiliser `FEATURE_COLUMNS` (DRY).
- **Autres commandes possibles** sur le même modèle : calcul des métriques réelles en production, promotion d'une version, alimentation de la base de dev.

### Points restant ouverts

- **Déclenchement** : manuel, planifié (cron), sur condition de données (N nouvelles commandes labellisées), sur dégradation des métriques en production, ou sur changement de code (CI) ?
- **Image Docker** : une seule image partagée lancée avec deux commandes (`serve` / `train`), ou deux images distinctes ?
- **Promotion en production** et **rechargement du modèle par l'API** (repris de l'ADR-0002) : automatiques ou manuels ?

---

## ADR-0004 — Sur quelle plateforme déployer l'application

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

L'application se lance directement avec Python, sur le poste du développeur :

- l'**API de prédiction** est un processus permanent (`serve`), qui écoute sur `127.0.0.1:8000` ;
- l'**entraînement** est une commande ponctuelle (`train`) ;
- les **runs MLflow** et le **modèle** sont des fichiers locaux.

La plateforme doit :

- **faire tourner la même chose partout**, du poste de développement à la prod, sans réécriture ;
- **accueillir de nouveaux composants** à mesure que l'application grandit (base de données, serveur de suivi des modèles) ;
- **rester simple à exploiter** pour une petite équipe, sans CI/CD pour l'instant ;
- **permettre plus tard** HTTPS et une mise en service progressive des nouvelles versions.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Docker Compose (en local, puis sur un VPS) | Un seul `docker-compose.yml` sert partout. Une seule commande pour tout démarrer. Mêmes images en dev et en prod | Une seule machine : pas de mise à l'échelle automatique, pas de bascule vers une autre machine en cas de panne |
| B. Kubernetes (k3s sur une VM, ou cluster managé) | Standard de l'industrie. Déploiements progressifs (rolling, canary) et redémarrage des services intégrés. `/health` et `/health/ready` sont déjà prêts pour ses sondes | Lourd pour trois services. Manifestes à écrire et à maintenir. Courbe d'apprentissage importante |
| C. Conteneurs managés (Cloud Run, Azure Container Apps, ECS Fargate) | HTTPS et mise à l'échelle fournis par le service | Dépend d'un fournisseur cloud (écarté par l'ADR-0005). Les volumes de MLflow et PostgreSQL sont à remplacer par des services managés |
| D. PaaS (Render, Railway, Fly.io) | Déploiement depuis le dépôt en quelques clics | Peu de contrôle. Offres gratuites limitées. PostgreSQL et stockage persistant souvent payants |
| E. Installation directe, sans conteneur (Python et PostgreSQL installés sur la machine) — situation actuelle | Aucune couche Docker | Environnement différent sur chaque machine, dépendances installées à la main, aucune parité entre dev et prod |

### Décision

**Option A : Docker et Docker Compose, d'abord en local, puis sur un VPS avec le même `docker-compose.yml`.**

- **Mêmes images, même fichier compose** en local et sur le VPS : seule la configuration (`.env`) change d'une machine à l'autre.
- **Kubernetes et les services managés sont écartés** tant que l'application tient sur une machine et n'a pas besoin de mise à l'échelle.

### Conséquences

- **À créer** :
  - un `Dockerfile` pour l'application (Python 3.13, comme `requires-python`), dont la commande par défaut est `serve` et qui peut aussi lancer `train` ;
  - un `.dockerignore` qui exclut au minimum `.env`, `.venv/`, `notebooks/` et les artéfacts ;
  - un `docker-compose.yml` avec les services `api`, `mlflow` et `db`. PostgreSQL démarre avec un profil `prod`, puisqu'en dev les commandes sont en mémoire (ADR-0001) ;
  - un healthcheck Docker qui interroge `/health`.
- **Le `docker-compose.yml` est le descripteur de déploiement.** Tout service de prod y figure. Le choix entre dev et prod se fait par `ENVIRONMENT` et `COMPOSE_PROFILES`.
- **Écoute réseau** : dans le conteneur, l'API écoute sur `0.0.0.0` (la CLI utilise `127.0.0.1` par défaut, ce qui la rendrait injoignable depuis l'hôte). C'est le compose qui limite l'exposition (ADR-0005).
- **Dépendances** : `requirements.txt` contient l'environnement complet de développement, y compris `pywin32`, qui ne s'installe pas dans une image Linux. Il faut séparer les dépendances d'exécution (`requirements.txt`) et de développement (`requirements-dev.txt`).
- **Déploiement manuel en attendant la CI/CD** : sur la machine cible, récupérer le code (`git pull`) puis lancer `docker compose up -d --build`. Plus tard, la CI construira les images et les publiera dans un registre (par exemple GitHub Container Registry) : le VPS n'aura plus qu'à les télécharger.
- **Un reverse proxy (Caddy ou Traefik) s'ajoutera devant l'API sur le VPS**, pour HTTPS (ADR-0007) et pour répartir le trafic entre deux versions (ADR-0006).
- **Redémarrage automatique** : `restart: unless-stopped` sur chaque service. Le service Docker doit démarrer avec la machine.
- **Limite assumée : une seule machine est un point de défaillance unique.** Les sauvegardes des volumes deviennent indispensables (ADR-0008). Une fois l'application conteneurisée, un passage ultérieur à Kubernetes ou à un service managé reste possible sans réécrire le code.

### Points restant ouverts

- **Construction des images** sur le VPS lui-même ou dans la CI avec un registre : à trancher avec la mise en place de la CI/CD.

---

## ADR-0005 — Cloud, on-premise ou local

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

L'application ne tourne aujourd'hui que sur le poste du développeur. Il n'existe ni serveur, ni hébergement, ni nom de domaine. Il faut décider où tournera l'environnement de production.

Éléments à prendre en compte :

- **Budget** : projet de M2, idéalement sans coût.
- **Données** : les commandes sont synthétiques (`order_generator.py`) et ne contiennent aucune donnée personnelle. Aucune contrainte réglementaire forte pour l'instant.
- **Disponibilité** : aucune exigence de service continu à ce stade. L'API doit pouvoir être montrée, puis devenir joignable depuis Internet.
- **Maîtrise** : l'équipe veut comprendre et contrôler sa plateforme.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Local (poste du développeur, pile `ENVIRONMENT=prod` lancée avec Docker Compose) | Gratuit et immédiat. Aucune exposition sur Internet | Pas joignable de l'extérieur. S'arrête avec le poste. Pas une vraie prod |
| B. VPS (serveur virtuel loué : OVHcloud, Scaleway, Hetzner…) | Quelques euros par mois. Accès complet à la machine. Même Docker qu'en local. Hébergeur européen possible | Système, sécurité, mises à jour et sauvegardes à notre charge |
| C. On-premise (serveur de l'école ou de l'entreprise) | Pas de location. Données sur place | Dépend de la disponibilité et des règles du propriétaire du serveur. Accès depuis l'extérieur à négocier |
| D. Cloud public avec services managés (Azure, AWS, GCP) | Base, stockage, secrets et HTTPS gérés par le fournisseur. Mise à l'échelle | Coût variable. Configuration propre à chaque fournisseur et dépendance envers lui. Surdimensionné pour ce projet |

### Décision

**Option A pour l'instant : la production tourne en local. Passage possible sur un VPS (option B) plus tard. Pas de cloud public avec services managés.**

- **En local**, la « prod » est la pile `ENVIRONMENT=prod` (avec PostgreSQL) lancée sur un poste. C'est suffisant pour les démonstrations.
- **Sur un VPS ensuite**, quand l'API devra être joignable depuis Internet, sans changer d'outil (même Docker Compose, ADR-0004).

**Services cloud : aucun n'est retenu.** Si un passage au cloud est décidé plus tard, voici la correspondance des composants :

| Composant | Aujourd'hui | Azure | AWS | GCP |
|---|---|---|---|---|
| API | conteneur `api` | Container Apps | ECS Fargate | Cloud Run |
| Base des commandes | conteneur `db` + volume | Azure Database for PostgreSQL | RDS PostgreSQL | Cloud SQL |
| Artéfacts MLflow | volume `mlflow_data` | Blob Storage | S3 | Cloud Storage |
| Secrets | fichier `.env` | Key Vault | Secrets Manager | Secret Manager |

### Conséquences

- **En local, rien ne doit être joignable depuis le réseau.** Les ports publiés par le compose (API 8000, MLflow 5000, PostgreSQL) doivent n'écouter que sur la machine (`127.0.0.1:8000:8000`). Sinon, un portable connecté à un réseau Wi-Fi partagé les exposerait (ADR-0008). Hors Docker, `serve` écoute déjà sur `127.0.0.1` par défaut.
- **Sur le VPS** : choisir un hébergeur européen (données hébergées dans l'Union européenne), durcir le serveur (ADR-0008) et réserver un nom de domaine pour le certificat HTTPS (ADR-0007).
- **Dimensionnement indicatif du VPS**, à vérifier une fois l'image construite : 2 vCPU et 4 Go de mémoire (l'entraînement scikit-learn charge les données en mémoire, et les dépendances incluent MLflow, pandas et pyarrow).
- **Pas de garantie de disponibilité** : acceptable à ce stade du projet.

### Points restant ouverts

- **Hébergeur du VPS** et **nom de domaine**.
- **Moment de la bascule** vers le VPS.

---

## ADR-0006 — Quelle stratégie de déploiement

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

Aucun processus de mise en service n'existe aujourd'hui :

- **Nouvelle version du code** : il faut arrêter l'API, récupérer le code, puis la relancer. Le service est coupé pendant l'opération, et revenir en arrière demande de relancer manuellement l'ancienne version.
- **Nouvelle version du modèle** : `train` écrase le `.joblib`. L'API garde l'ancien modèle en mémoire jusqu'à son prochain redémarrage, puis sert le nouveau à **toutes** les requêtes. Il n'y a aucune comparaison avec la version précédente, et aucun retour arrière possible, puisque l'ancien fichier a été écrasé.
- **Version du modèle** : `model_version` vient de la configuration (`MODEL_VERSION`) et non du modèle chargé. On ne peut donc pas attribuer une prédiction à une version précise.

On veut mettre une nouvelle version en service en limitant l'impact d'une mauvaise version, et pouvoir revenir en arrière rapidement.

Contraintes :

- **une seule machine**, sans orchestrateur ;
- **pas de CI/CD** ;
- **pas de supervision** : aucune métrique n'est collectée sur les prédictions servies.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Recreate (arrêt de l'ancienne version, démarrage de la nouvelle) | Le plus simple : `docker compose up -d` remplace le conteneur | Coupure de quelques secondes. Retour arrière = redéployer l'ancienne version. Tout le trafic subit une mauvaise version |
| B. Blue/green (deux versions en parallèle, bascule du trafic) | Bascule et retour arrière instantanés | Deux piles complètes en parallèle. Tout le trafic bascule d'un coup |
| C. Rolling (remplacement progressif des instances) | Sans coupure | Nécessite plusieurs instances et un orchestrateur (écarté par l'ADR-0004) |
| D. Canary (une petite part du trafic sur la nouvelle version, augmentée si tout va bien) | Une mauvaise version ne touche qu'une partie des requêtes. Décision fondée sur des mesures réelles | Routage pondéré nécessaire. Il faut des métriques pour décider d'augmenter la part ou d'arrêter |
| E. Feature flags (nouveau code livré désactivé, activé par configuration) | Activation et désactivation sans redéployer. Désactivation immédiate en cas de problème | Code conditionnel à maintenir, puis à retirer. Ne protège pas d'une image qui ne démarre pas |

### Décision

**Option D : canary release.** Une nouvelle version reçoit d'abord une petite part du trafic. Cette part augmente si les mesures sont bonnes, et retombe à zéro sinon. Le canary s'applique à deux niveaux.

- **Le modèle** (le niveau le plus risqué dans notre cas) :
  - l'entraînement inscrit la nouvelle version avec l'alias `challenger`, et non directement comme version servie ;
  - l'API charge les deux versions (`champion` et `challenger`) et envoie au challenger la part des prédictions fixée par la variable `CANARY_PERCENT` (0 = tout le trafic sur le champion) ;
  - l'affectation dépend de l'identifiant de la commande (par exemple `hash(order_id) % 100 < CANARY_PERCENT`), pour qu'une commande soit toujours prédite par la même version ;
  - **montée en charge** progressive, par exemple 5 %, puis 25 %, puis 50 % ;
  - **promotion** : déplacer l'alias `champion` sur le challenger. **Retour arrière** : remettre `CANARY_PERCENT` à 0, sans redéploiement ni réentraînement.
- **Le code de l'API** :
  - sur le VPS, le reverse proxy (ADR-0004) répartit le trafic entre l'ancienne et la nouvelle image de l'API, selon un poids qui augmente par étapes ;
  - **retour arrière** : remettre le poids de la nouvelle image à 0, puis arrêter son conteneur ;
  - tant qu'il n'y a pas de reverse proxy (en local), le remplacement de l'image se fait en mode recreate.

Raisons :

- **Aucun orchestrateur nécessaire** : le canary du modèle se règle dans l'API et par configuration, celui de l'image dans le reverse proxy. Cela convient à une seule machine.
- **Dans un projet de Machine Learning, le risque principal est le modèle** : un modèle moins bon ne fait planter aucun service, il produit simplement de mauvaises prédictions. Le canary le détecte sur une petite part du trafic, avant qu'il ne touche toutes les commandes.
- **La décision de promotion s'appuie sur des données réelles** : chaque prédiction est enregistrée avec la version du modèle qui l'a produite, ce qui permet de comparer le champion et le challenger sur le même trafic.
- **Retour arrière immédiat** : une seule valeur de configuration à changer, sans attendre un nouveau déploiement.

### Conséquences

- **Prérequis** : registre MLflow et version réelle du modèle (ADR-0002), enregistrement des prédictions (ADR-0001), reverse proxy sur le VPS pour le canary de l'image (ADR-0004).
- **À implémenter** (rien n'est encore en place) :
  - l'inscription avec l'alias `challenger` dans l'entraînement ;
  - la variable `CANARY_PERCENT` dans `config.py` et `.env.example` ;
  - le chargement des deux versions et la répartition dans l'API (`MLPredict` reçoit les deux modèles, ou un service de routage les enveloppe) ;
  - un `order_id` toujours présent : il est facultatif dans `OrderEntity`, et l'API devra en générer un s'il est absent ;
  - une commande CLI de promotion (déplacer l'alias `champion`) ;
  - un endpoint `GET /model` qui expose la model card, avec la version du challenger, ainsi que cette version dans `/health/ready` ;
  - la pondération du trafic entre deux images dans la configuration du reverse proxy.
- **Des métriques sont nécessaires pour piloter le canary** : comparaison de la latence et des erreurs dès le départ, puis de la qualité (f1, précision…) une fois le résultat réel des commandes connu. Cela dépend de la remontée du label réel (point ouvert de l'ADR-0001) et de la supervision. Tant que la supervision n'existe pas, la comparaison se fait par requête sur les prédictions enregistrées.
- **Deux modèles en mémoire** pendant un canary : la consommation mémoire de l'API double pendant cette période.
- **Volume minimal** : avec peu de trafic, une petite part ne donne pas assez de prédictions pour comparer les versions. La durée de chaque étape doit tenir compte du volume réel.

### Points restant ouverts

- **Paliers** de montée en charge et **durée** de chaque palier.
- **Seuils de promotion** : écart de latence, de taux d'erreur et de qualité acceptable entre challenger et champion.
- **Promotion manuelle ou automatique.**

---

## ADR-0007 — Comment sécuriser les entrées et les sorties de l'API

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

L'API expose `GET /health`, `GET /health/ready` et `POST /predict`, **sans authentification**. Elle écoute par défaut sur `127.0.0.1` : elle n'est donc pas joignable depuis le réseau pour l'instant, mais elle devra l'être depuis Internet.

État des entrées et des sorties :

- **Validation partielle** : le corps de `/predict` est la dataclass du domaine `OrderEntity`. FastAPI vérifie les types, mais pas les bornes (une heure à 42 est acceptée) ni les valeurs des catégories, et il ignore silencieusement les champs en trop.
- **Erreurs** : aucun format d'erreur commun. Un modèle absent donne une réponse 503 avec `detail`, et une erreur inattendue donne la réponse 500 par défaut de FastAPI.
- **Sorties** : `/predict` déclare un `response_model`, qui limite la réponse aux champs de `PredictionEntity`.
- **Aucune limite** de débit ni de taille de requête, aucun HTTPS. La documentation `/docs` est publique.
- **Aucun test** de l'API : le projet n'a pas de dossier `tests/`.

Une fois l'API exposée, les risques sont :

- **appels non autorisés** : n'importe qui pourrait demander des prédictions ou envoyer de fausses commandes ;
- **données invalides ou malveillantes** : variables manquantes, valeurs hors limites, champs inattendus ;
- **saturation** : requêtes volumineuses, rafales de requêtes ;
- **fuite d'informations** par les messages d'erreur (traces, détails internes) ;
- **interception** des échanges sur le réseau.

### Options considérées

Pour contrôler qui appelle l'API :

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Aucune authentification, API joignable seulement depuis un réseau privé (situation actuelle) | Rien à gérer | Inapplicable dès que l'API est sur Internet (VPS) |
| B. Clé d'API dans un en-tête (`X-API-Key`) + HTTPS | Simple, adapté aux appels de machine à machine. Une clé par client, révocable | Clé statique : à protéger et à renouveler. Pas de droits fins |
| C. OAuth2 / JWT + HTTPS | Jetons à durée limitée, droits par périmètre (scopes), révocation centralisée | Il faut un fournisseur d'identité à mettre en place et à exploiter. Plus complexe à tester en local |
| D. Certificats clients (mTLS) | Authentification très forte | Gestion d'une autorité de certification et des certificats de chaque client |

### Décision

**L'authentification dépend de l'environnement :**

| Environnement | Authentification | Quand |
|---|---|---|
| Dev | **Option B** : clé d'API dans l'en-tête `X-API-Key` | dès maintenant |
| Prod | **Option C** : OAuth2 / JWT, jetons émis par un fournisseur d'identité | plus tard, au passage en prod exposée sur Internet. D'ici là, la prod locale (ADR-0005) utilise aussi la clé d'API |

- **En dev, une clé d'API** : simple à mettre en place, aucun service supplémentaire, facile à utiliser dans les tests et avec `curl`.
- **En prod, OAuth2 / JWT** : jetons à durée limitée (une fuite n'a d'effet que jusqu'à l'expiration du jeton), droits par périmètre, gestion des clients centralisée chez le fournisseur d'identité.
- **Le mode est choisi par configuration** (`AUTH_MODE=api_key` ou `oauth2`), dans la racine de composition. Les routes ne dépendent que d'une dépendance FastAPI d'authentification, qui ne change pas de nom d'un mode à l'autre. Passer de B à C ne modifie donc pas les routes.
- **HTTPS** dans les deux cas dès que l'API sort de `127.0.0.1`.

Ces choix s'accompagnent des mesures suivantes sur les entrées et les sorties.

**Entrées**

- **Clé d'API (dev)** : obligatoire sur toutes les routes métier (`/predict` et les suivantes), via l'en-tête `X-API-Key`. Elle est comparée en temps constant (`secrets.compare_digest`) aux clés autorisées. Une clé absente ou inconnue donne une réponse 401 sans détail.
- **Jeton OAuth2 (prod)** : obligatoire sur les mêmes routes, via l'en-tête `Authorization: Bearer <jeton>`. L'API vérifie la signature du jeton avec les clés publiques du fournisseur d'identité (JWKS), ainsi que l'émetteur (`iss`), l'audience (`aud`), l'expiration (`exp`) et le périmètre requis (par exemple `predict`). Jeton absent, invalide ou expiré : 401. Périmètre insuffisant : 403. Les clients sont des machines, donc le flux OAuth2 utilisé est `client_credentials`.
- **Routes publiques** : `/health` et `/health/ready` restent sans authentification dans les deux modes, car Docker et le reverse proxy s'en servent pour vérifier l'état du service.
- **HTTPS** : sur le VPS, le reverse proxy (Caddy ou Traefik, ADR-0004) porte le certificat (Let's Encrypt) et redirige HTTP vers HTTPS. Le port de l'API n'est plus publié directement : seul le proxy est joignable. En local, HTTP sur `127.0.0.1` reste acceptable.
- **Validation stricte** :
  - un schéma Pydantic dédié à l'API, distinct de l'entité du domaine `OrderEntity`, qui reste une dataclass sans dépendance à FastAPI ;
  - variable manquante ou en trop : erreur 422 (`extra="forbid"`) ;
  - bornes contrôlées (`hour` entre 0 et 23, `day_of_week` entre 0 et 6, `weekend` et `stock_available` dans {0, 1}, distances, poids et montants positifs, `carrier_capacity` entre 0 et 1) ;
  - valeurs énumérées contrôlées (`weather`, `delivery_zone`, `customer_type`), sur les modalités connues du générateur ;
  - si une route par lot est ajoutée, elle est limitée à 1000 commandes ;
  - contraintes `CHECK` en base en seconde barrière (ADR-0001).
- **Limitation du débit** : nombre de requêtes par minute et taille maximale des requêtes, appliqués par le reverse proxy.

**Sorties**

- **Erreurs sans détail interne** : un format d'erreur unique (`code`, `message`). Un gestionnaire d'exceptions global transforme toute erreur inattendue en `internal_error` avec un message générique. La trace ne va que dans les logs du serveur.
- **Réponses limitées aux champs du contrat** : `response_model` (déjà utilisé sur `/predict`) filtre tout champ en trop.
- **Logs sans contenu sensible** : les logs d'accès n'enregistrent pas le corps des requêtes, ni jamais la clé d'API ou le jeton. Ils peuvent enregistrer l'identifiant du client (`sub` du jeton, ou nom associé à la clé). Les commandes ne contiennent aucune donnée personnelle.
- **Pas de CORS** : aucune interface web n'appelle l'API, donc aucun site tiers ne peut l'appeler depuis un navigateur.

### Conséquences

- **À implémenter maintenant (dev)** :
  - une dépendance FastAPI (`Depends`) d'authentification sur les routes métier, avec l'implémentation par clé d'API ;
  - les variables `AUTH_MODE` (défaut `api_key`) et `API_KEYS` dans `config.py`, `.env` et `.env.example` ;
  - le schéma Pydantic d'entrée et sa conversion vers `OrderEntity` ;
  - le gestionnaire d'erreurs global ;
  - des tests des réponses 401 et 422 (le projet n'a pas encore de dossier `tests/`).
- **À implémenter plus tard (prod)** :
  - l'implémentation OAuth2 de la même dépendance : vérification du jeton (par exemple avec PyJWT et le JWKS du fournisseur) ;
  - les variables `OAUTH2_ISSUER`, `OAUTH2_AUDIENCE` et l'URL du JWKS ;
  - l'enregistrement de chaque client chez le fournisseur d'identité, avec son périmètre ;
  - des tests des réponses 401 et 403 avec des jetons signés par une clé de test ;
  - le service reverse proxy dans le compose, pour HTTPS sur le VPS.
- **Garde-fou** : au démarrage, l'API refuse `AUTH_MODE=api_key` quand `ENVIRONMENT=prod`, une fois le passage à OAuth2 effectué. La clé d'API ne peut donc pas rester active en prod par oubli.
- **Un service de plus en prod** : le fournisseur d'identité (auto-hébergé comme Keycloak, ou externe) doit être disponible pour que les clients obtiennent un jeton. L'API, elle, ne l'appelle pas à chaque requête : elle garde en cache les clés publiques du JWKS.
- **Versionnage de l'API** : les routes métier passent sous un préfixe `/v1` (`/v1/predict`) avant la mise en ligne, pour pouvoir faire évoluer le contrat sans casser les clients.
- **Documentation client** : l'en-tête `X-API-Key` (dev) puis `Authorization: Bearer` (prod) est documenté dans le README et dans le schéma OpenAPI généré par FastAPI (schémas de sécurité `apiKey`, puis `oauth2`).
- **Secrets** : les clés d'API et le secret client OAuth2 ne sont jamais dans le dépôt ni dans les images. Ils sont gérés comme les mots de passe de la base (ADR-0008).

### Points restant ouverts

- **Fournisseur d'identité** pour la prod : auto-hébergé (Keycloak) ou service externe (Auth0, Entra ID…) ?
- **Moment de la bascule** vers OAuth2, à lier au passage sur le VPS (ADR-0005).
- **Durée de vie des jetons** et **périmètres** à définir (par exemple `predict`, `model:read`).
- **Documentation `/docs` en prod** : publique, protégée, ou désactivée ?
- **Renouvellement des clés d'API** en dev : fréquence et procédure.

---

## ADR-0008 — Comment sécuriser l'accès aux données

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

Données manipulées aujourd'hui par l'application :

- **les commandes** : générées au démarrage et gardées en mémoire. Rien n'est écrit sur disque ;
- **le modèle** : `express_delivery_model.joblib`, avec `metrics.json` et `features.json`, dans `notebooks/artifacts/`. Un `.joblib` est un pickle : le charger exécute le code qu'il contient. Quiconque peut écrire dans ce dossier peut donc faire exécuter du code par l'API ;
- **les runs MLflow** : fichiers locaux sur le poste qui lance l'entraînement, sans authentification ;
- **la configuration** : fichier `.env`, exclu de git par `.gitignore`. `.env.example` ne contient aucune valeur. L'application n'utilise encore aucun secret (ni mot de passe de base, ni clé d'API).

Aucune sauvegarde n'existe. Les commandes ne contiennent aucune donnée personnelle : le RGPD ne s'applique pas aujourd'hui.

Les risques vont augmenter dès que l'application stockera des données durablement, utilisera des secrets ou sera joignable depuis le réseau. Les règles d'accès doivent être fixées avant ces évolutions, pas après.

### Options considérées

Pour les droits d'accès à la base :

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Un seul compte administrateur partagé (comportement par défaut de l'image PostgreSQL) | Simple | Une fuite du mot de passe donne tous les droits : suppression des tables, création de comptes |
| B. Des comptes séparés, chacun avec le minimum de droits | Chaque service n'a que les droits utiles : une fuite a un impact limité | Comptes et droits à créer par un script d'initialisation |
| C. Accès par identité cloud (IAM) avec un service managé | Pas de mot de passe statique | Nécessite le cloud, écarté par l'ADR-0005 |

### Décision

**Les droits d'accès à la base dépendent de l'environnement :**

| Environnement | Droits d'accès | Pourquoi |
|---|---|---|
| Dev | **Option A** : un seul compte administrateur | Données synthétiques et jetables, base accessible uniquement depuis le poste. Aucun script de droits à maintenir pour démarrer |
| CI | **Option B** : comptes séparés, comme en prod | Les erreurs de droits (l'API qui tente de créer une table, l'entraînement qui tente d'écrire) doivent être détectées avant la prod |
| Prod | **Option B** : comptes séparés, chacun avec le minimum de droits | Une fuite de mot de passe n'a qu'un impact limité |

En dev, les commandes sont en mémoire (ADR-0001) : l'option A ne concerne que les bases PostgreSQL lancées sur un poste de développement, par exemple pour tester le cycle complet avec `docker compose`.

**En dev, l'option A est encadrée** :

- la base n'écoute que sur `127.0.0.1` ;
- elle ne contient que des données synthétiques, jamais une copie des données de prod ;
- son mot de passe est propre au dev et n'est jamais réutilisé en CI ni en prod.

**En CI et en prod, l'option B est complétée par l'isolement réseau, la gestion des secrets, la protection des artéfacts et des sauvegardes.**

- **Moindre privilège dans PostgreSQL** :

  | Compte | Droits | Utilisé par |
  |---|---|---|
  | administrateur (`POSTGRES_USER`) | tous | administration et création du schéma uniquement |
  | `api_user` | lecture et écriture sur `orders` et `predictions`, aucun droit de modifier le schéma | l'API |
  | `training_reader` | lecture seule sur `orders` | la commande `train` (l'entraînement ne fait que lire) |

- **Isolement réseau** :
  - PostgreSQL et MLflow ne sont pas joignables depuis l'extérieur. Leurs ports ne sont publiés que sur `127.0.0.1`, et les commandes lancées depuis un poste passent par un tunnel SSH ;
  - pare-feu du VPS : seuls SSH (22), HTTP (80) et HTTPS (443) sont ouverts ;
  - connexion SSH par clé uniquement, sans mot de passe.
- **MLflow** : interface et API réservées à l'équipe, par tunnel SSH. Si une exposition devient nécessaire : authentification intégrée de MLflow (`mlflow server --app-name basic-auth`) derrière HTTPS.
- **Artéfacts du modèle** :
  - l'API ne charge un modèle que depuis le registre MLflow (ADR-0002) ou un dossier en lecture seule pour elle ;
  - le format `skops`, déjà utilisé par `MLTrainer` pour MLflow (`skops_trusted_types`), est préféré au pickle, car il n'exécute pas de code arbitraire au chargement.
- **Secrets** :
  - `.env` jamais versionné (déjà exclu par `.gitignore`) ni copié dans les images (`.dockerignore` à créer, ADR-0004) ;
  - sur le VPS, fichier lisible par son seul propriétaire (`chmod 600`) ;
  - mots de passe différents par environnement, changés en cas de fuite.
- **Chiffrement en transit** : HTTPS pour l'API (ADR-0007). Les échanges avec PostgreSQL et MLflow restent sur le réseau Docker interne de la machine, ou passent par le tunnel SSH.
- **Sauvegardes** : export quotidien de la base (`pg_dump`) et archive du volume `mlflow_data`, stockés hors du VPS, avec un test de restauration régulier.
- **Génération de données synthétiques** : interdite quand `ENVIRONMENT=prod`, ou soumise à une confirmation explicite.

### Conséquences

- **Deux configurations de base à maintenir** : en dev, le compte administrateur créé par l'image PostgreSQL (`POSTGRES_USER`) suffit ; en CI et en prod, le script d'initialisation crée les comptes séparés. Le code ne fait pas la différence : il reçoit simplement des URL de connexion différentes.
- **Les erreurs de droits n'apparaissent pas en dev** : en administrateur, tout est permis. C'est la CI, configurée comme la prod, qui les détecte.
- **À implémenter**, au moment de la mise en place de la base et de MLflow :
  - un script d'initialisation PostgreSQL qui crée les comptes et leurs droits, exécuté en CI et en prod uniquement ;
  - des variables de connexion distinctes pour l'API et pour l'entraînement (en dev, elles peuvent pointer vers le même compte administrateur) ;
  - la création du schéma par les migrations, pas au démarrage de l'API (le compte de l'API ne peut pas créer de tables) ;
  - les ports liés à `127.0.0.1` dans le compose ;
  - le chargement du modèle en `skops` dans `MlflowModelRepository` ;
  - le garde-fou de la génération de données ;
  - le script de sauvegarde.
- **Cohérence avec l'ADR-0002**, qui prévoit un utilisateur PostgreSQL par base : ce principe s'applique en CI et en prod.
- **Si des données réelles sont utilisées un jour** : application du RGPD (minimisation des données, durée de conservation, registre des traitements).

### Points restant ouverts

- **Emplacement des sauvegardes** hors du VPS.
- **Chiffrement du disque** du VPS.
- **Fréquence de renouvellement** des mots de passe.
