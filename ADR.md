# Architecture Decision Records

## ADR-0001 — Stockage des commandes

**Status :** Accepté
**Date :** 26/10/2026
**Révision :** 20/11/2026. Les commandes restent dans le MongoDB des analystes, alimenté par l'ERP : l'application n'a pas de base propre et n'enregistre pas ses prédictions. La première version (PostgreSQL en CI et en prod) est abandonnée.

### Contexte

L'API expose `POST /predict` : elle reçoit une commande, renvoie une prédiction, et **n'enregistre rien**.

Au départ, le seul stockage de commandes est `InMemoryOrderRepository`, un dictionnaire Python rempli au démarrage de l'entraînement par le générateur synthétique. L'interface `OrderRepositoryInterface` (`domain/interface/`) déclare `save`, `get` et `get_training_data()`, et l'implémentation est choisie dans la racine de composition `core/core.py`.

Les commandes réelles existent déjà ailleurs : l'ERP les envoie, avec leur label, dans le **MongoDB des analystes**. Ce MongoDB n'est pas une base de l'ERP : il en reçoit les données **dans un seul sens** (ERP → MongoDB), sans aucun lien retour (ADR-0009).

La question est donc : l'application a-t-elle besoin de **sa propre base** de commandes ? Deux besoins sont possibles :

- **entraîner** le modèle sur des commandes labellisées ;
- **garder une trace des prédictions servies** (commande, prédiction, version du modèle), pour l'audit ou pour mesurer la qualité du modèle sur le trafic réel.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Aucune base propre : l'entraînement lit le MongoDB des analystes, l'API n'enregistre rien | Rien à installer ni à maintenir. Une seule source de vérité, déjà alimentée par l'ERP | Aucune trace des prédictions servies : pas d'audit, pas de mesure de la qualité sur le trafic réel |
| B. MongoDB des analystes, où l'API écrit aussi ses prédictions | Pas de nouveau serveur | Mélange les données de l'ERP et celles de l'application dans une base faite pour l'analyse |
| C. PostgreSQL propre à l'application (en mémoire en dev) | Trace complète des prédictions, schéma imposé, jointures | Un serveur de plus à maintenir. Les commandes existent déjà dans MongoDB : on les aurait en double |
| D. SQLite | Un seul fichier, aucun service | Un seul écrivain à la fois, une seule machine |

### Décision

**Option A : l'application n'a pas de base propre. Les commandes sont lues dans le MongoDB des analystes, et l'API n'enregistre ni les commandes ni les prédictions.**

Raisons :

- **Les données existent déjà et sont alimentées en continu** : l'ERP écrit dans le MongoDB des analystes. Créer une autre base reviendrait à stocker les mêmes commandes deux fois.
- **Le seul besoin retenu est l'entraînement** : on réentraîne avec les nouvelles données, on compare le nouveau modèle (challenger) au modèle en service (champion) sur les mêmes commandes récentes, et il ne devient champion que s'il fait mieux (ADR-0009, ADR-0010). Cette comparaison n'a besoin d'aucune trace des prédictions servies.
- **Aucun risque pour l'ERP** : le lien va dans un seul sens, de l'ERP vers MongoDB. Rien de ce que fait l'entraînement ne remonte vers l'ERP.
- **L'accès est maîtrisé** : l'équipe obtient le compte administrateur de ce MongoDB par l'alternant qui le maintient, ou le reprend lors du transfert de compte à son départ. Elle crée ensuite un compte en lecture seule pour l'entraînement (ADR-0007).

**Par environnement** (`TRAINING_SOURCE_URL`, ADR-0009) :

| Environnement | Source des commandes |
|---|---|
| Dev, tests unitaires | `memory://` : générateur synthétique (`InMemoryOrderRepository`) |
| Dev, cycle complet | MongoDB de dev, alimenté par l'ETL simulé (profil `etl`) |
| Test | MongoDB de test, avec authentification, alimenté par l'ETL simulé |
| Prod | MongoDB des analystes, compte en lecture seule |

### Conséquences

- **L'API reste sans état** : une prédiction n'existe que dans la réponse et dans les logs. On ne peut ni auditer une prédiction passée, ni mesurer la qualité du modèle sur le trafic réel.
- **La qualité d'un modèle se juge avant sa mise en service**, sur le jeu de test tiré de MongoDB (ADR-0010). Pendant un canary (ADR-0005), la comparaison du stable et du canary se fait sur les logs de l'API.
- **Deux implémentations de `OrderRepositoryInterface`** : `InMemoryOrderRepository` (dev, tests) et `MongoOrderRepository` (test, prod), choisies par `TRAINING_SOURCE_URL` dans `core/core.py`. Le métier ne dépend pas du moteur.
- **Validation à la lecture** : MongoDB n'impose aucun schéma. `MongoOrderRepository` convertit chaque document en `OrderEntity` et écarte, en le comptant, tout document incomplet ou mal typé (ADR-0009).
- **Dépendance au MongoDB des analystes** : s'il est indisponible, l'entraînement échoue et le modèle en service reste en place. L'API, elle, n'en dépend pas.
- **Aucun serveur de base de données pour l'application.** Le seul PostgreSQL du système est la base interne d'Airflow (ADR-0010), qui ne contient aucune donnée de l'application.

### Points restant ouverts

- **Tracer les prédictions** si un besoin d'audit ou de suivi en production apparaît : une collection dédiée, dans un MongoDB propre à l'application plutôt que dans celui des analystes.
- **Mesurer la performance réelle** en reliant une prédiction au label arrivé plus tard dans MongoDB, par `order_id` : cela suppose que le client envoie à l'API l'identifiant de l'ERP.

---

## ADR-0002 — Stockage des artefacts de modèle

**Status :** Accepté
**Date :** 26/10/2026
**Révision :** 20/11/2026. La décision décrit ce qui est en place : modèle servi depuis un fichier sur le volume partagé, MLflow en stockage fichiers. Le Model Registry et PostgreSQL sont reportés.

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

**Option B pour le modèle servi, avec MLflow Tracking pour l'historique des entraînements. Le Model Registry (option C) est reporté.**

Le modèle servi est un fichier. MLflow conserve à côté l'historique de tous les entraînements, sans serveur ni base de données.

| | Modèle servi (lu par l'API) | Historique des entraînements (MLflow) |
|---|---|---|
| Contenu | `express_delivery_model.joblib`, avec `metrics.json` et `features.json` | Un run par entraînement : paramètres, métriques (y compris celles du modèle en service, `champion_*`) et une copie du modèle |
| Écrit par | `train`, via `FileModelRepository`, **seulement si le nouveau modèle est promu** (ADR-0010) | `train`, via `MlflowTracker`, à **chaque** entraînement |
| Emplacement avec Docker (dev, test, prod) | `/data/artifacts/` sur le volume `app_data` (`MODEL_PATH`) | `/data/mlruns` sur le même volume (`MLFLOW_TRACKING_URI`, stockage fichiers) |
| Emplacement sans Docker | `notebooks/artifacts/` | Dossier `mlruns/` du répertoire courant |

Le service `mlflow` des composes ne lance que l'interface web (`mlflow ui`) sur ce dossier. Ni l'entraînement ni l'API ne passent par lui.

Raisons :

- **L'API ne dépend d'aucun service pour démarrer** : elle lit un fichier sur le volume. Si MLflow est arrêté, elle sert quand même les prédictions.
- **Une seule machine** (ADR-0003, ADR-0004) : un volume Docker partagé entre `train` et `api` suffit à transmettre le modèle.
- **L'historique sans infrastructure** : le stockage fichiers de MLflow fournit l'interface, la comparaison des runs et une copie de chaque modèle, sans base ni serveur à maintenir.
- **Le Model Registry n'apporte rien tant qu'un seul modèle est servi** : ses alias `champion` / `challenger` servaient à désigner deux versions servies en même temps. Le canary de l'ADR-0005 s'en passe, avec deux fichiers (`MODEL_PATH`, `CANARY_MODEL_PATH`).
- **Revenir sur ce choix reste peu coûteux** : l'API ne connaît que `ModelRepositoryInterface`, et l'entraînement `ExperimentTrackerInterface`. Passer au registre revient à écrire une classe `MlflowModelRepository` et à la choisir dans `core/core.py`.

### Conséquences

- **Un seul volume à sauvegarder** : `app_data` contient le modèle servi et tout l'historique MLflow (ADR-0007). Il est lié à la machine hôte.
- **Stockage fichiers de MLflow** : MLflow 3 le déprécie au profit d'une base. Il doit être autorisé explicitement (`MLFLOW_ALLOW_FILE_STORE=true` dans les composes).
- **Version du modèle** : `model_version` vient encore de la configuration (`MODEL_VERSION`), pas du fichier. Deux modèles successifs peuvent donc porter la même version. Le lien fiable vers le modèle exact est le `run_id` MLflow, écrit dans les logs de `train` et dans son résultat JSON.
- **Retour arrière manuel** : le fichier servi est écrasé à chaque promotion, mais chaque run MLflow garde une copie du modèle. Pour revenir en arrière, on recharge celle du run voulu (`mlflow.sklearn.load_model("runs:/<run_id>/model")`), on l'écrit à l'emplacement de `MODEL_PATH`, puis on redémarre l'API. Aucune commande ne l'automatise encore.
- **Prise en compte d'un nouveau modèle** : l'API charge le modèle une seule fois, au démarrage. Un nouveau modèle est servi après `docker compose restart api`, que le DAG lance en prod (ADR-0010).
- **Abandonné par rapport à la première version de cet ADR** : la base `mlflow` sur PostgreSQL, les utilisateurs `commandes_user` et `mlflow_user`, le serveur MLflow intermédiaire pour les fichiers des modèles, et les alias `champion` / `challenger`.

### Points restant ouverts

- **Passage au Model Registry** : quand chaque prédiction devra porter une version réelle, ou quand l'application tournera sur plusieurs machines. Les métadonnées passeront alors sur une base SQL (MLflow ne prend pas MongoDB, ADR-0006), et les fichiers sur un stockage compatible S3.
- **Version automatique** : remplacer `MODEL_VERSION` par une valeur liée au modèle (`run_id`, date d'entraînement), sans attendre le registre.
- **Commande de retour arrière** vers le modèle d'un run donné.
- **Reproductibilité des données** : enregistrer dans le run la période ou une empreinte du jeu d'entraînement.

---

## ADR-0003 — Quelle plateforme de déploiement ?

**Status :** Accepté
**Date :** 26/10/2026
**Révision :** 20/11/2026. Un fichier Compose par environnement (dev, test, prod) au lieu d'un `docker-compose.yml` unique.

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
| A. Docker Compose (en local, puis sur un VPS) | Même outil partout. Une seule commande pour démarrer un environnement. Même image en test et en prod | Une seule machine : pas de mise à l'échelle automatique, pas de bascule vers une autre machine en cas de panne |
| B. Kubernetes (k3s sur une VM, ou cluster managé) | Standard de l'industrie. Déploiements progressifs (rolling, canary) et redémarrage des services intégrés. `/health` et `/health/ready` sont déjà prêts pour ses sondes | Lourd pour trois services. Manifestes à écrire et à maintenir. Courbe d'apprentissage importante |
| C. Conteneurs managés (Cloud Run, Azure Container Apps, ECS Fargate) | HTTPS et mise à l'échelle fournis par le service | Dépend d'un fournisseur cloud (écarté par l'ADR-0004). Les volumes de MLflow et PostgreSQL sont à remplacer par des services managés |
| D. PaaS (Render, Railway, Fly.io) | Déploiement depuis le dépôt en quelques clics | Peu de contrôle. Offres gratuites limitées. PostgreSQL et stockage persistant souvent payants |
| E. Installation directe, sans conteneur (Python et PostgreSQL installés sur la machine) — situation actuelle | Aucune couche Docker | Environnement différent sur chaque machine, dépendances installées à la main, aucune parité entre dev et prod |

### Décision

**Option A : Docker Compose, avec un fichier Compose par environnement (`dev`, `test`, `prod`). La prod tourne d'abord en local, puis sur un VPS, avec le même `docker-compose.prod.yml`.**

| Environnement | Fichiers | Image de l'application | Données d'entraînement | Services en plus de `api`, `train` et `mlflow` |
|---|---|---|---|---|
| Dev (sur son poste, `feat/*`, `dev`) | `docker-compose.dev.yml` + `.env.dev` | Construite, étape `dev` (avec pytest et ruff) | En mémoire par défaut ; MongoDB et ETL simulés avec le profil `etl` | `mongodb`, `etl-simulator` (profil `etl`) |
| Test (`release/*`, `hotfix/*`) | `docker-compose.test.yml` + `.env.test` | Construite, étape `test`, identique à `prod` | MongoDB de test avec authentification, alimenté par l'ETL simulé | `mongodb`, `etl-simulator` |
| Prod (`main`) | `docker-compose.prod.yml` + `.env.prod` | Publiée sur GitHub Container Registry par la CD, choisie par `APP_VERSION` | MongoDB de l'ERP, externe, en lecture seule (ADR-0009) | Airflow et sa base, `docker-proxy` (ADR-0010) |

- **Un fichier complet par environnement**, plutôt qu'un fichier unique avec des profils ou des surcharges : les environnements n'ont ni les mêmes services ni la même origine d'image. Chaque fichier se lit seul et montre exactement ce qui tourne.
- **La même image de la validation à la prod** : l'étape `test` du `Dockerfile` est identique à `prod`. Ce qui a été validé sur une release est ce qui part en production.
- **Seule la configuration change d'une machine à l'autre** : le fichier `.env.<environnement>`, passé à Compose avec `--env-file` et synchronisé avec les GitHub Environments `development`, `test` et `production` (`scripts/env.ps1`).
- **Kubernetes et les services managés sont écartés** tant que l'application tient sur une machine et n'a pas besoin de mise à l'échelle.

### Conséquences

- **`Dockerfile` multi-étapes** (Python 3.13, comme `requires-python`) : `base` installe les dépendances d'exécution et le code ; `dev` y ajoute `requirements-dev.txt` et tout le dépôt ; `test` et `prod` retirent pip et tournent avec `appuser` (UID 1000). La commande par défaut est `serve`, et le service `train` lance `train` à la demande (ADR-0008).
- **`.dockerignore`** : exclut `.env` et `.env.*`, `.git/`, `.venv/`, `notebooks/`, les modèles, les runs MLflow et l'ETL simulé.
- **Réglages communs recopiés** dans les trois fichiers (durcissement, volume, healthcheck) : une modification commune se fait dans les trois. C'est le prix de fichiers lisibles seuls.
- **Écoute réseau** : dans le conteneur, l'API écoute sur `0.0.0.0` (la CLI utilise `127.0.0.1` par défaut, ce qui la rendrait injoignable depuis l'hôte). Les ports ne sont publiés que sur `127.0.0.1` (ADR-0004).
- **Dépendances séparées** : `requirements.txt` pour l'exécution, `requirements-dev.txt` pour le développement. Les images `test` et `prod` ne contiennent que l'exécution.
- **Publication par la CD, déploiement manuel** : la fusion d'une release dans `main` construit l'image et la publie sur GitHub Container Registry, sans la déployer. Sur la machine de prod, on met à jour `APP_VERSION` dans `.env.prod`, puis on lance `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d`.
- **Un reverse proxy (Caddy ou Traefik) s'ajoutera devant l'API sur le VPS**, pour HTTPS (ADR-0007).
- **Redémarrage automatique** : `restart: unless-stopped` sur chaque service permanent. Le service Docker doit démarrer avec la machine.
- **Limite assumée : une seule machine est un point de défaillance unique.** Les sauvegardes des volumes deviennent indispensables (ADR-0007). Une fois l'application conteneurisée, un passage ultérieur à Kubernetes ou à un service managé reste possible sans réécrire le code.

### Points restant ouverts

- **Déploiement automatique sur le VPS** par la CD : aujourd'hui, elle publie l'image sans la déployer.
- **Reverse proxy** à ajouter dans `docker-compose.prod.yml` au passage sur le VPS.

---

## ADR-0004 — Cloud, on-premise ou local ?

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
| A. Local (poste du développeur, pile `docker-compose.prod.yml` lancée avec Docker Compose) | Gratuit et immédiat. Aucune exposition sur Internet | Pas joignable de l'extérieur. S'arrête avec le poste. Pas une vraie prod |
| B. VPS (serveur virtuel loué : OVHcloud, Scaleway, Hetzner…) | Quelques euros par mois. Accès complet à la machine. Même Docker qu'en local. Hébergeur européen possible | Système, sécurité, mises à jour et sauvegardes à notre charge |
| C. On-premise (serveur de l'école ou de l'entreprise) | Pas de location. Données sur place | Dépend de la disponibilité et des règles du propriétaire du serveur. Accès depuis l'extérieur à négocier |
| D. Cloud public avec services managés (Azure, AWS, GCP) | Base, stockage, secrets et HTTPS gérés par le fournisseur. Mise à l'échelle | Coût variable. Configuration propre à chaque fournisseur et dépendance envers lui. Surdimensionné pour ce projet |

### Décision

**Option A pour l'instant : la production tourne en local. Passage possible sur un VPS (option B) plus tard. Pas de cloud public avec services managés.**

- **En local**, la « prod » est la pile `docker-compose.prod.yml` lancée sur un poste. C'est suffisant pour les démonstrations.
- **Sur un VPS ensuite**, quand l'API devra être joignable depuis Internet, sans changer d'outil (même Docker Compose, ADR-0003).

**Services cloud : aucun n'est retenu.** Si un passage au cloud est décidé plus tard, voici la correspondance des composants :

| Composant | Aujourd'hui | Azure | AWS | GCP |
|---|---|---|---|---|
| API | conteneur `api` | Container Apps | ECS Fargate | Cloud Run |
| Commandes (MongoDB des analystes) | service externe | Azure Cosmos DB for MongoDB | Amazon DocumentDB | MongoDB Atlas |
| Modèle et runs MLflow | volume `app_data` | Blob Storage | S3 | Cloud Storage |
| Secrets | fichier `.env` | Key Vault | Secrets Manager | Secret Manager |

### Conséquences

- **En local, rien ne doit être joignable depuis le réseau.** Les ports publiés par le compose (API 8000, MLflow 5000, Airflow 8080) doivent n'écouter que sur la machine (`127.0.0.1:8000:8000`). Sinon, un portable connecté à un réseau Wi-Fi partagé les exposerait (ADR-0007). Hors Docker, `serve` écoute déjà sur `127.0.0.1` par défaut.
- **Sur le VPS** : choisir un hébergeur européen (données hébergées dans l'Union européenne), durcir le serveur (ADR-0007) et réserver un nom de domaine pour le certificat HTTPS (ADR-0007).
- **Dimensionnement indicatif du VPS**, à vérifier une fois l'image construite : 2 vCPU et 4 Go de mémoire (l'entraînement scikit-learn charge les données en mémoire, et les dépendances incluent MLflow, pandas et pyarrow).
- **Pas de garantie de disponibilité** : acceptable à ce stade du projet.

### Points restant ouverts

- **Hébergeur du VPS** et **nom de domaine**.
- **Moment de la bascule** vers le VPS.

---

## ADR-0005 — Quelle stratégie de déploiement ?

**Status :** Accepté
**Date :** 26/10/2026
**Révision :** 20/11/2026. Canary à 90/10 réparti dans l'API par `CANARY_PERCENT`, sans reverse proxy ni Model Registry.

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
| C. Rolling (remplacement progressif des instances) | Sans coupure | Nécessite plusieurs instances et un orchestrateur (écarté par l'ADR-0003) |
| D. Canary (une petite part du trafic sur la nouvelle version, augmentée si tout va bien) | Une mauvaise version ne touche qu'une partie des requêtes. Décision fondée sur des mesures réelles | Routage pondéré nécessaire. Il faut des métriques pour décider d'augmenter la part ou d'arrêter |
| E. Feature flags (nouveau code livré désactivé, activé par configuration) | Activation et désactivation sans redéployer. Désactivation immédiate en cas de problème | Code conditionnel à maintenir, puis à retirer. Ne protège pas d'une image qui ne démarre pas |

### Décision

**Option D : canary release à 90/10. Le nouveau modèle (le canary) reçoit d'abord 10 % des commandes, et le modèle en service (le stable) les 90 % restants. Si le canary passe les critères, il reçoit 100 % des commandes et devient le stable.**

Une seule variable, `CANARY_PERCENT` (de 0 à 100, `0` par défaut), fixe la part des commandes envoyée au canary.

| Étape | `CANARY_PERCENT` | Stable (version 1) | Canary (version 2) |
|---|---|---|---|
| Nouveau modèle déposé, inactif | `0` | 100 % | 0 % |
| Essai | `10` | 90 % | 10 % |
| Généralisation, si l'essai passe les critères | `100` | 0 % | 100 % |
| Retour arrière, à tout moment | `0` | 100 % | 0 % |

- **Où se fait la répartition** : dans l'API, qui charge les deux modèles. Il n'y a pas besoin de reverse proxy, ce qui convient à une seule machine (ADR-0003).
- **Affectation d'une commande** : le canary répond si `zlib.crc32(order_id.encode()) % 100 < CANARY_PERCENT`. Une même commande tombe donc toujours du même côté. On utilise `crc32` et non `hash()` de Python, car `hash()` change à chaque démarrage du processus.
- **Par commande, pas encore par utilisateur** : l'API ne connaît pas ses clients tant que l'authentification n'est pas en place (ADR-0007). Ensuite, la même formule s'appliquera à l'identifiant du client (`sub` du jeton), pour qu'un client voie toujours la même version.
- **Changer d'étape** : modifier `CANARY_PERCENT` dans `.env.<environnement>` (et dans le GitHub Environment correspondant, ADR-0003), puis recréer l'API (`docker compose -f docker-compose.<environnement>.yml --env-file .env.<environnement> up -d api`). Il ne faut ni nouvelle image ni réentraînement. `docker compose restart api` ne suffit pas, car il garde les anciennes variables.
- **Avant le canary, la qualité** : un nouveau modèle ne devient canary que s'il a un meilleur score que le stable sur le même jeu de test, tiré des données de l'ERP (ADR-0009, ADR-0010).
- **Pendant le canary, le comportement réel** : sur ses commandes, le canary ne doit avoir ni plus d'erreurs ni plus de latence que le stable, et sa part de commandes éligibles ne doit pas s'écarter anormalement. **Le passage à 100 % est une décision manuelle**, prise après lecture des mesures.
- **L'image de l'API**, elle, est remplacée en mode recreate (on change `APP_VERSION`, puis on lance `up -d`). Retour arrière : remettre l'`APP_VERSION` précédente, toujours disponible sur GitHub Container Registry. Un canary entre deux images demandera un reverse proxy, au passage sur le VPS.

Raisons :

- **Dans un projet de Machine Learning, le risque principal est le modèle** : un modèle moins bon ne fait planter aucun service, il produit simplement de mauvaises prédictions. Le canary limite ce risque à 10 % des commandes, le temps de le vérifier sur le vrai trafic.
- **Aucune infrastructure à ajouter** : pas de reverse proxy ni de Model Registry. La répartition tient en une ligne de code et une variable, lue par le `Settings` existant.
- **Retour arrière en une variable**, sans rebuild, sans réentraînement et sans attente de la CI.

### Conséquences

- **Deux modèles** : `MODEL_PATH` et `MODEL_VERSION` pour le stable, `CANARY_MODEL_PATH` et `CANARY_MODEL_VERSION` pour le canary. Ces variables, ainsi que `CANARY_PERCENT`, sont ajoutées dans `config.py`, dans `.env.example` et les modèles `.env.*.example`, dans la section `environment` des trois composes et dans les GitHub Environments.
- **Cycle d'un modèle** :
  - `train` écrit le modèle promu à `CANARY_MODEL_PATH`, au lieu d'écraser le stable, et l'essai commence à 0 % ;
  - après la généralisation, le canary est copié à `MODEL_PATH`, et `CANARY_PERCENT` revient à 0. Il devient le stable du prochain essai ;
  - le DAG de l'ADR-0010 sera adapté à ce fonctionnement.
- **Chaque prédiction indique le modèle qui a répondu** : la réponse porte sa version (`model_version`), et un log par requête donne l'`order_id`, la version, la latence et l'erreur éventuelle. Comme l'API n'enregistre pas ses prédictions (ADR-0001), ce sont ces logs qui servent à comparer les deux modèles.
- **`order_id` toujours présent** : il est facultatif dans `OrderEntity`, donc l'API en génère un (`uuid4`) s'il est absent, et le renvoie dans la réponse.
- **La répartition est assemblée par la racine de composition** (`core/core.py`), qui charge les deux modèles. Le métier ne lit jamais la configuration lui-même.
- **Tests** : pytest couvre 0 %, 100 %, et vérifie que la répartition à 10 % est stable pour un même `order_id`.
- **Deux modèles en mémoire** pendant un essai : la consommation mémoire de l'API double pendant cette période.
- **État de l'implémentation** :
  - **fait** : la répartition dans l'API (`CanaryPredict`, assemblé par `build_prediction_service`), les variables `CANARY_*` et le log par prédiction. Si `CANARY_PERCENT` > 0 mais qu'il n'y a pas de modèle canary, tout va au stable ;
  - **reste à faire** : `train` et le DAG écrivent encore le modèle promu à `MODEL_PATH` (ADR-0010). En attendant, on dépose un canary en lançant `train` avec `MODEL_PATH` pointant vers `CANARY_MODEL_PATH`, sans comparaison avec le stable.
- **Limites assumées** :
  - avec peu de trafic, 10 % donnent peu de commandes, et l'essai doit durer assez longtemps pour être significatif ;
  - chaque changement de `CANARY_PERCENT` recrée l'API, ce qui la coupe quelques secondes.

### Points restant ouverts

- **Seuils chiffrés** des critères : écart de taux d'erreur, de latence et de part d'éligibles acceptable entre le canary et le stable.
- **Durée minimale de l'essai**, ou nombre minimal de commandes servies par le canary.
- **Palier intermédiaire** (par exemple 50 %) si un passage direct de 10 % à 100 % paraît trop brutal.
- **Canary de l'image de l'API** par un reverse proxy, au passage sur le VPS.
- **Affectation par client** une fois l'authentification en place (ADR-0007).

---

## ADR-0006 — PostgreSQL, MongoDB, autre ?

**Status :** Accepté
**Date :** 17/11/2026
**Révision :** 20/11/2026. MongoDB retenu : celui des analystes, déjà en place. PostgreSQL est abandonné pour les données de l'application.

### Contexte

L'ADR-0001 conclut que l'application n'a pas de base propre : ses seules données sont les commandes labellisées qui servent à l'entraînement. Cet ADR tranche le moteur de ces données : s'appuyer sur le MongoDB des analystes, déjà en place, ou monter une base relationnelle à côté.

Ce qu'on sait :

- **le MongoDB des analystes existe et est alimenté** : l'ERP y envoie ses commandes et leur label, dans un seul sens (ADR-0009) ;
- **l'équipe peut en devenir administratrice** : l'alternant qui le maintient lui donne l'accès, ou lui transfère son compte à son départ ;
- **le besoin est une lecture simple** : toutes les commandes labellisées, triées par date pour le jeu de test (ADR-0009). Aucune jointure, aucune mise à jour, aucune écriture par l'application ;
- **le volume est petit** : quelques milliers de commandes, sur une machine (ADR-0003, ADR-0004).

Cet ADR ne concerne pas les bases internes des outils : Airflow impose une base SQL pour ses métadonnées (ADR-0010), et MLflow stocke ses runs en fichiers (ADR-0002).

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. PostgreSQL (relationnel), propre à l'application | Schéma et contraintes imposés par la base. Jointures et transactions ACID | Un serveur de plus à installer, sécuriser et sauvegarder. Les commandes devraient être copiées depuis MongoDB : deux bases pour les mêmes données |
| B. MySQL / MariaDB (relationnel) | Mêmes atouts relationnels | Mêmes inconvénients que PostgreSQL |
| C. MongoDB des analystes (orienté documents), déjà en place | Existe déjà et reçoit les données de l'ERP en continu. Rien à installer. Accès administrateur obtenu par l'équipe. Documents proches des objets Python | Aucun schéma imposé : la validation se fait à la lecture. Pas de jointures simples (inutiles aujourd'hui) |
| D. Autre NoSQL : Redis, Cassandra, Elasticsearch | Très performants sur leur cas d'usage (cache, écritures massives, recherche) | Aucun de ces cas d'usage n'est le nôtre, et il faudrait aussi copier les données |
| E. SQLite | Un fichier, aucun service | Copie des données, un seul écrivain, une seule machine |

### Décision

**Option C : MongoDB, celui des analystes, déjà en place. Pas de base PostgreSQL pour les données de l'application.**

Raisons :

- **La base existe et le système est en place** : l'ERP l'alimente, l'ETL tourne, et `MongoOrderRepository` la lit déjà (ADR-0009). Une base relationnelle demanderait de copier ces commandes et de maintenir cette copie.
- **Nos besoins n'utilisent pas les atouts du relationnel** : l'application ne fait que lire des commandes labellisées. Sans prédictions stockées (ADR-0001), il n'y a ni jointure ni mise à jour transactionnelle à garantir.
- **Isolée de l'ERP** : le lien va de l'ERP vers MongoDB, jamais dans l'autre sens. Lire cette base ne peut rien casser côté ERP.
- **L'absence de schéma est compensée à la lecture** : chaque document est validé et converti en `OrderEntity`. Un document incomplet est écarté et compté, jamais utilisé en silence (ADR-0009).
- **Un serveur de moins à exploiter** : pas de PostgreSQL applicatif à sécuriser, sauvegarder et mettre à jour.

### Conséquences

- **Un seul moteur pour les données de l'application : MongoDB.** PostgreSQL n'existe dans le système que comme base interne d'Airflow (ADR-0010).
- **Comptes MongoDB** (ADR-0007) : le compte administrateur, détenu par l'équipe après le transfert, sert uniquement à l'administration ; `training_reader`, en lecture seule, sert à l'entraînement.
- **Validation obligatoire à la lecture**, dans `MongoOrderRepository` uniquement.
- **Sauvegardes** : vérifier celles des analystes, sinon un `mongodump` quotidien (ADR-0007, ADR-0009).
- **Model Registry de MLflow** : s'il remplace un jour le stockage fichiers (ADR-0002), il demandera une base SQL, car MLflow ne prend pas MongoDB.

### Points restant ouverts

- **Date et modalités du transfert** du compte administrateur, avant la fin du contrat de l'alternant.
- **Tests sur un vrai MongoDB en CI** (service container), en plus de la collection factice.

---

## ADR-0007 — Comment sécuriser les entrées, les sorties et l'accès à la donnée

**Status :** Accepté
**Date :** 26/10/2026
**Révision :** 20/11/2026. Fusion des deux ADR qui traitaient ces sujets séparément (entrées et sorties de l'API, accès aux données), pour suivre la numérotation du cours. Comptes et sauvegardes portés sur MongoDB : l'application n'a pas de base PostgreSQL (ADR-0001, ADR-0006).

Cet ADR couvre deux surfaces, traitées l'une après l'autre dans chaque partie :

- **les entrées et les sorties de l'API** : qui peut l'appeler, ce qu'elle accepte, ce qu'elle renvoie ;
- **l'accès aux données** : comptes de la base, modèle, MLflow, secrets et sauvegardes.

### Contexte

#### Entrées et sorties de l'API

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

#### Accès aux données

Données manipulées aujourd'hui par l'application :

- **les commandes** : générées au démarrage et gardées en mémoire. Rien n'est écrit sur disque ;
- **le modèle** : `express_delivery_model.joblib`, avec `metrics.json` et `features.json`, dans `notebooks/artifacts/`. Un `.joblib` est un pickle : le charger exécute le code qu'il contient. Quiconque peut écrire dans ce dossier peut donc faire exécuter du code par l'API ;
- **les runs MLflow** : fichiers locaux sur le poste qui lance l'entraînement, sans authentification ;
- **la configuration** : fichier `.env`, exclu de git par `.gitignore`. `.env.example` ne contient aucune valeur. L'application n'utilise encore aucun secret (ni mot de passe de base, ni clé d'API).

Aucune sauvegarde n'existe. Les commandes ne contiennent aucune donnée personnelle : le RGPD ne s'applique pas aujourd'hui.

Les risques vont augmenter dès que l'application stockera des données durablement, utilisera des secrets ou sera joignable depuis le réseau. Les règles d'accès doivent être fixées avant ces évolutions, pas après.

### Options considérées

#### Entrées et sorties de l'API

Pour contrôler qui appelle l'API :

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Aucune authentification, API joignable seulement depuis un réseau privé (situation actuelle) | Rien à gérer | Inapplicable dès que l'API est sur Internet (VPS) |
| B. Clé d'API dans un en-tête (`X-API-Key`) + HTTPS | Simple, adapté aux appels de machine à machine. Une clé par client, révocable | Clé statique : à protéger et à renouveler. Pas de droits fins |
| C. OAuth2 / JWT + HTTPS | Jetons à durée limitée, droits par périmètre (scopes), révocation centralisée | Il faut un fournisseur d'identité à mettre en place et à exploiter. Plus complexe à tester en local |
| D. Certificats clients (mTLS) | Authentification très forte | Gestion d'une autorité de certification et des certificats de chaque client |

#### Accès aux données

Pour les droits d'accès à la base :

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Un seul compte administrateur partagé, ou aucune authentification (comportement par défaut de l'image MongoDB) | Simple | Une fuite du mot de passe donne tous les droits : suppression des tables, création de comptes |
| B. Des comptes séparés, chacun avec le minimum de droits | Chaque service n'a que les droits utiles : une fuite a un impact limité | Comptes et droits à créer par un script d'initialisation |
| C. Accès par identité cloud (IAM) avec un service managé | Pas de mot de passe statique | Nécessite le cloud, écarté par l'ADR-0004 |

### Décision

#### Entrées et sorties de l'API

**L'authentification dépend de l'environnement :**

| Environnement | Authentification | Quand |
|---|---|---|
| Dev | **Option B** : clé d'API dans l'en-tête `X-API-Key` | dès maintenant |
| Prod | **Option C** : OAuth2 / JWT, jetons émis par un fournisseur d'identité | plus tard, au passage en prod exposée sur Internet. D'ici là, la prod locale (ADR-0004) utilise aussi la clé d'API |

- **En dev, une clé d'API** : simple à mettre en place, aucun service supplémentaire, facile à utiliser dans les tests et avec `curl`.
- **En prod, OAuth2 / JWT** : jetons à durée limitée (une fuite n'a d'effet que jusqu'à l'expiration du jeton), droits par périmètre, gestion des clients centralisée chez le fournisseur d'identité.
- **Le mode est choisi par configuration** (`AUTH_MODE=api_key` ou `oauth2`), dans la racine de composition. Les routes ne dépendent que d'une dépendance FastAPI d'authentification, qui ne change pas de nom d'un mode à l'autre. Passer de B à C ne modifie donc pas les routes.
- **HTTPS** dans les deux cas dès que l'API sort de `127.0.0.1`.

Ces choix s'accompagnent des mesures suivantes sur les entrées et les sorties.

**Entrées**

- **Clé d'API (dev)** : obligatoire sur toutes les routes métier (`/predict` et les suivantes), via l'en-tête `X-API-Key`. Elle est comparée en temps constant (`secrets.compare_digest`) aux clés autorisées. Une clé absente ou inconnue donne une réponse 401 sans détail.
- **Jeton OAuth2 (prod)** : obligatoire sur les mêmes routes, via l'en-tête `Authorization: Bearer <jeton>`. L'API vérifie la signature du jeton avec les clés publiques du fournisseur d'identité (JWKS), ainsi que l'émetteur (`iss`), l'audience (`aud`), l'expiration (`exp`) et le périmètre requis (par exemple `predict`). Jeton absent, invalide ou expiré : 401. Périmètre insuffisant : 403. Les clients sont des machines, donc le flux OAuth2 utilisé est `client_credentials`.
- **Routes publiques** : `/health` et `/health/ready` restent sans authentification dans les deux modes, car Docker et le reverse proxy s'en servent pour vérifier l'état du service.
- **HTTPS** : sur le VPS, le reverse proxy (Caddy ou Traefik, ADR-0003) porte le certificat (Let's Encrypt) et redirige HTTP vers HTTPS. Le port de l'API n'est plus publié directement : seul le proxy est joignable. En local, HTTP sur `127.0.0.1` reste acceptable.
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

#### Accès aux données

**Les droits d'accès à la base dépendent de l'environnement :**

| Environnement | Droits d'accès | Pourquoi |
|---|---|---|
| Dev | **Option A** : MongoDB de dev sans authentification | Données synthétiques et jetables, base accessible uniquement depuis le poste. Aucun script de droits à maintenir pour démarrer |
| Test | **Option B** : comptes séparés, comme en prod (`docker/mongo/init-users.js`) | Les erreurs de droits (l'API qui tente de créer une table, l'entraînement qui tente d'écrire) doivent être détectées avant la prod |
| Prod | **Option B** : comptes séparés, chacun avec le minimum de droits | Une fuite de mot de passe n'a qu'un impact limité |

En dev, les commandes sont en mémoire par défaut (ADR-0001) : l'option A ne concerne que le MongoDB du profil `etl` de `docker-compose.dev.yml`, lancé pour tester le cycle complet.

**En dev, l'option A est encadrée** :

- la base n'écoute que sur `127.0.0.1` ;
- elle ne contient que des données synthétiques, jamais une copie des données de prod ;
- son mot de passe est propre au dev et n'est jamais réutilisé en CI ni en prod.

**En test et en prod, l'option B est complétée par l'isolement réseau, la gestion des secrets, la protection des artéfacts et des sauvegardes.**

- **Moindre privilège dans MongoDB** (l'API n'a aucun accès à une base, ADR-0001) :

  | Compte | Droits | Utilisé par |
  |---|---|---|
  | administrateur | tous | administration uniquement. En prod, le compte que l'alternant transmet à l'équipe |
  | `training_reader` | lecture seule (`read`) sur `livraison_express` | la commande `train` (l'entraînement ne fait que lire) |
  | `etl_writer` | lecture et écriture (`readWrite`) sur `livraison_express` | l'ETL simulé, en test uniquement. En prod, c'est l'ERP qui écrit |

- **Isolement réseau** :
  - MongoDB et MLflow ne sont pas joignables depuis l'extérieur. Leurs ports ne sont publiés que sur `127.0.0.1`, et les commandes lancées depuis un poste passent par un tunnel SSH ;
  - pare-feu du VPS : seuls SSH (22), HTTP (80) et HTTPS (443) sont ouverts ;
  - connexion SSH par clé uniquement, sans mot de passe.
- **MLflow** : interface et API réservées à l'équipe, par tunnel SSH. Si une exposition devient nécessaire : authentification intégrée de MLflow (`mlflow server --app-name basic-auth`) derrière HTTPS.
- **Artéfacts du modèle** :
  - l'API ne charge un modèle que depuis le registre MLflow (ADR-0002) ou un dossier en lecture seule pour elle ;
  - le format `skops`, déjà utilisé par `MLTrainer` pour MLflow (`skops_trusted_types`), est préféré au pickle, car il n'exécute pas de code arbitraire au chargement.
- **Secrets** :
  - `.env` jamais versionné (déjà exclu par `.gitignore`) ni copié dans les images (`.dockerignore` à créer, ADR-0003) ;
  - sur le VPS, fichier lisible par son seul propriétaire (`chmod 600`) ;
  - mots de passe différents par environnement, changés en cas de fuite.
- **Chiffrement en transit** : HTTPS pour l'API (partie « Entrées et sorties de l'API »). Les échanges avec MongoDB et MLflow restent sur le réseau Docker interne de la machine, ou passent par le tunnel SSH.
- **Sauvegardes** : celles du MongoDB des analystes, à vérifier (sinon un `mongodump` quotidien), l'export de la base d'Airflow (`pg_dump`) et l'archive du volume `app_data` (modèle et runs MLflow), stockés hors du VPS, avec un test de restauration régulier.
- **Génération de données synthétiques** : interdite quand `APP_ENV=prod`, ou soumise à une confirmation explicite.

### Conséquences

#### Entrées et sorties de l'API

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
- **Garde-fou** : au démarrage, l'API refuse `AUTH_MODE=api_key` quand `APP_ENV=prod`, une fois le passage à OAuth2 effectué. La clé d'API ne peut donc pas rester active en prod par oubli.
- **Un service de plus en prod** : le fournisseur d'identité (auto-hébergé comme Keycloak, ou externe) doit être disponible pour que les clients obtiennent un jeton. L'API, elle, ne l'appelle pas à chaque requête : elle garde en cache les clés publiques du JWKS.
- **Versionnage de l'API** : les routes métier passent sous un préfixe `/v1` (`/v1/predict`) avant la mise en ligne, pour pouvoir faire évoluer le contrat sans casser les clients.
- **Documentation client** : l'en-tête `X-API-Key` (dev) puis `Authorization: Bearer` (prod) est documenté dans le README et dans le schéma OpenAPI généré par FastAPI (schémas de sécurité `apiKey`, puis `oauth2`).
- **Secrets** : les clés d'API et le secret client OAuth2 ne sont jamais dans le dépôt ni dans les images. Ils sont gérés comme les mots de passe de la base (partie « Accès aux données »).

#### Accès aux données

- **Trois configurations à maintenir** : en dev, MongoDB sans authentification ; en test, `docker/mongo/init-users.js` crée les comptes séparés ; en prod, l'équipe les crée avec le compte administrateur. Le code ne fait pas la différence : il reçoit simplement une URL de connexion différente (`TRAINING_SOURCE_URL`).
- **Les erreurs de droits n'apparaissent pas en dev** : sans authentification, tout est permis. C'est l'environnement de test, configuré comme la prod, qui les détecte.
- **À implémenter**, au moment de la mise en place de la base et de MLflow :
  - les comptes MongoDB de prod, créés par l'équipe une fois le compte administrateur obtenu (en test, `init-users.js` le fait déjà) ;
  - les ports liés à `127.0.0.1` dans le compose ;
  - le chargement du modèle en `skops` dans `MlflowModelRepository` ;
  - le garde-fou de la génération de données ;
  - le script de sauvegarde.
- **Si des données réelles sont utilisées un jour** : application du RGPD (minimisation des données, durée de conservation, registre des traitements).

### Points restant ouverts

- **Fournisseur d'identité** pour la prod : auto-hébergé (Keycloak) ou service externe (Auth0, Entra ID…) ?
- **Moment de la bascule** vers OAuth2, à lier au passage sur le VPS (ADR-0004).
- **Durée de vie des jetons** et **périmètres** à définir (par exemple `predict`, `model:read`).
- **Documentation `/docs` en prod** : publique, protégée, ou désactivée ?
- **Renouvellement des clés d'API** en dev : fréquence et procédure.
- **Emplacement des sauvegardes** hors du VPS.
- **Chiffrement du disque** du VPS.
- **Fréquence de renouvellement** des mots de passe.

---

## ADR-0008 — Où et comment exécuter l'entraînement du modèle

**Status :** Accepté
**Date :** 26/10/2026

### Contexte

Le code de Machine Learning du notebook (`notebooks/project_test_v1_final_final2.ipynb`) a été extrait dans `src/app/core/learning/` : pipeline (`MLPipeline`), découpage (`TrainTestSplitter`), entraînement (`MLTrainer`), prédiction (`MLPredict`) et contrat des features (`order_feature.py`). Le notebook reste dans le dépôt comme trace de l'exploration.

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

**Option B : l'entraînement est une commande en ligne de commande (`python -m src.app train`), dans le même dépôt que l'API, exécutée dans un processus séparé.**

- **Même dépôt, même `src/`** : l'API et l'entraînement partagent le domaine (`OrderEntity`), le contrat des features (`FEATURE_COLUMNS`) et les repositories. Une évolution du modèle (une nouvelle variable, par exemple) modifie l'entraînement et la prédiction dans le même commit.
- **Deux points d'entrée distincts** : `serve` lance un service qui tourne en permanence. `train` est lancé, fait son travail, puis s'arrête avec un code de sortie (0 = succès, 1 = échec) exploitable par un cron ou la CI.
- **Isolation** : l'API n'importe jamais le code d'entraînement, et l'entraînement n'importe jamais FastAPI.

### Conséquences

- **Isolation** : la racine de composition `core/core.py` propose deux assemblages, `build_prediction_service` pour l'API et `build_training_service` pour l'entraînement. L'API n'importe ni MLflow ni le code d'entraînement, ce qu'un test vérifie (`test_api_does_not_import_training_code`).
- **Pas d'état global** : chaque point d'entrée crée sa configuration (`Settings`) et ses objets ; aucune classe métier ne lit la configuration elle-même. Les tests construisent leurs propres objets, sans configuration qui fuit d'un test à l'autre.
- **Imports relatifs dans tout le package** : le même code se lance avec `python -m src.app` depuis la racine du dépôt, et avec `python -m app` dans les images Docker, où il est copié sous le nom `app`.
- **Données d'entraînement** : `train` lit les commandes labellisées dans la base (ADR-0001) et non plus le générateur en mémoire. La génération de données synthétiques devient une commande séparée qui alimente la base de dev ; elle n'est pas du code de production.
- **Préparation des variables dans le pipeline** : le nettoyage et la préparation des variables restent intégrés au pipeline scikit-learn (`MLPipeline`) enregistré dans MLflow. Cela garantit un traitement identique à l'entraînement et à la prédiction.
- **La model card est construite à partir du contrat** : `TrainingService` utilise `FEATURE_COLUMNS` et lit le type de modèle dans le pipeline, sans rien recopier en dur (DRY).
- **Autres commandes possibles** sur le même modèle : calcul des métriques réelles en production, promotion d'une version, alimentation de la base de dev.

### Points restant ouverts

- **Déclenchement** : manuel, planifié (cron), sur condition de données (N nouvelles commandes labellisées), sur dégradation des métriques en production, ou sur changement de code (CI) ?
- **Image Docker** : une seule image partagée lancée avec deux commandes (`serve` / `train`), ou deux images distinctes ?
- **Promotion en production** et **rechargement du modèle par l'API** (repris de l'ADR-0002) : automatiques ou manuels ?

---

## ADR-0009 — Quelle base de l'ERP utiliser comme source des données d'entraînement

**Status :** Accepté
**Date :** 29/10/2026
**Révision :** 20/11/2026. Le MongoDB est celui des analystes, alimenté par l'ERP dans un seul sens ; le compte administrateur est transmis par l'alternant.

### Contexte

L'entraînement utilise aujourd'hui des commandes synthétiques générées en mémoire (ADR-0001). Pour s'entraîner sur des commandes réelles, il doit lire celles de l'ERP de l'entreprise, qui les écrit dans deux bases. Faute de serveur, cet ERP est simulé par le dossier `erp_prod_test`, **hors de ce dépôt** : il tourne dans ses propres conteneurs, comme s'il était sur une autre machine, et l'application le joint par le réseau.

**L'entraînement ne se fait qu'avec les données de l'ERP.** Un ETL met à jour les bases de l'ERP avec les commandes et leur label (la livraison express était-elle possible ?). Les commandes reçues par notre API ne servent pas à l'entraînement.

Cet ADR choisit **la base de l'ERP d'où l'entraînement lit les commandes**. L'ADR-0001 conclut que l'application n'a pas de base propre : cette base est la seule source des commandes.

Ce que disent les développeurs de l'ERP :

| | PostgreSQL | MongoDB |
|---|---|---|
| Rôle | Première base du logiciel, base de production | Base montée pour les Data Analysts, parce qu'ils cassaient la base de production |
| Historique | Depuis 2015 | Depuis 2023. L'historique antérieur n'a pas été copié |
| Schéma | Modifié en 2017 et en 2023 | Créé en 2023, après la dernière modification du schéma |
| Maintenance | Plus mise à jour depuis 2023 : l'administrateur a démissionné et n'a pas été remplacé | Maintenue par un alternant dont le contrat se termine bientôt |
| Autres usages | Utilisée aussi par une autre application critique pour l'entreprise | Aucun, hors analyse |

Ce que montre l'ERP simulé (`erp_prod_test`) :

- les commandes depuis 2023 sont les **mêmes dans les deux bases**, avec le même identifiant (`ERP-00011001`). Le flux courant est écrit dans les deux bases ;
- dans PostgreSQL, `weekend` vaut `NULL` avant le 1er juillet 2015 et `preparation_time_min` vaut `NULL` avant le 1er juillet 2017. Ces deux variables sont des entrées du modèle (`OrderEntity`) ;
- dans MongoDB, les commandes sont dans la collection `orders` de la base `livraison_express`, avec un index unique sur `order_id`. `order_date` y est stocké en `datetime` ;
- MongoDB tourne sans authentification et son port est publié sur toutes les interfaces.

Ce que la source doit permettre :

- **lire les commandes** sans gêner l'ERP ni l'autre application critique ;
- **fournir des données cohérentes avec le schéma actuel**, celui des commandes que l'API reçoit ;
- **filtrer par période**, pour entraîner et évaluer sur des fenêtres de dates ;
- **avoir un responsable** capable de créer un compte en lecture seule (ADR-0007) et de corriger un incident.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. PostgreSQL | Historique complet depuis 2015 (environ 11 000 commandes dans le simulateur). Schéma typé | Base de production partagée avec une application critique : une requête lourde ralentit les deux applications. Plus d'administrateur : personne pour créer le compte en lecture seule ni pour réagir à un incident. Valeurs `NULL` avant 2015 et 2017 à imputer ou à écarter. Les commandes 2015-2022 suivent d'anciens schémas |
| B. MongoDB | Base prévue pour l'analyse, isolée de la production : l'entraînement ne peut rien casser côté ERP. Données au schéma actuel, toutes les colonnes renseignées. Mêmes commandes que PostgreSQL depuis 2023, flux courant compris | Historique limité à 2023 → aujourd'hui (environ 1 000 commandes dans le simulateur). Mainteneur sur le départ. Aucun schéma imposé par la base |
| C. Les deux : MongoDB pour 2023 → aujourd'hui, PostgreSQL pour 2015-2022 | Historique complet sans charger la production en continu | Deux connecteurs à maintenir. Dépend toujours de PostgreSQL, donc d'un administrateur absent. Mélange de données issues de schémas différents |

### Décision

**Option B : l'entraînement lit les commandes dans MongoDB.**

Ce MongoDB est celui des analystes : ce n'est pas une base de l'ERP, il en reçoit les données **dans un seul sens** (ERP → MongoDB). Rien de ce que fait l'entraînement ne remonte vers l'ERP. L'équipe en obtient le compte administrateur par l'alternant qui le maintient, ou le reprend lors du transfert de compte à son départ.

- **Ne pas toucher à la production.** MongoDB existe justement pour que l'analyse ne passe plus par la base de production. Brancher l'entraînement sur PostgreSQL referait l'erreur qui a mené à sa création, avec en plus une application critique exposée.
- **Des données qui ressemblent à celles de l'API.** Les commandes depuis 2023 suivent le schéma actuel. Le modèle apprend sur des commandes comparables à celles qu'il évaluera. Les commandes de 2015 à 2017 auraient demandé d'imputer `weekend` et `preparation_time_min`.
- **Le volume suffit pour commencer.** Trois ans de commandes, complétés en continu par le flux courant. Le volume nécessaire se vérifie avec les métriques de l'entraînement (ADR-0002), pas a priori.
- **Un risque de maintenance qui se corrige.** Le départ de l'alternant se prépare : passation, documentation, reprise par l'équipe. L'absence d'administrateur de PostgreSQL ne dépend pas de l'équipe, et une erreur sur cette base touche une autre application.
- **L'option C est écartée pour l'instant.** Elle garde la dépendance à PostgreSQL pour un gain qui n'est pas démontré. Elle reste possible plus tard (voir « Points restant ouverts »).

**Le métier ne dépend pas du moteur** : l'entraînement ne connaît que `OrderRepositoryInterface`. Seule l'implémentation MongoDB contient du code `pymongo`.

**Cycle de réentraînement :**

1. l'ETL de l'ERP ajoute les nouvelles commandes labellisées dans MongoDB ;
2. `train` lit toutes les commandes labellisées et entraîne un nouveau modèle ;
3. le nouveau modèle et le modèle en service (`champion`) sont évalués **sur le même jeu de test** : les commandes les plus récentes, qui n'ont servi à entraîner aucun des deux ;
4. si le nouveau modèle a un meilleur score, il remplace le modèle en service (ADR-0010). Sinon, le modèle en service est conservé, et le prochain entraînement se fera avec les nouvelles données de l'ETL.

Comparer deux scores mesurés sur des jeux de test différents ne prouve rien : les nouvelles données peuvent simplement être plus faciles ou plus difficiles à prédire. D'où l'étape 3.

**L'ETL est un système externe** : il appartient à l'ERP, tourne à part, et notre application ne le lance jamais. `train` lit ce qui se trouve dans MongoDB au moment où il démarre.

**Par environnement :**

| Environnement | Source des commandes (`TRAINING_SOURCE_URL`) | Qui alimente MongoDB |
|---|---|---|
| Dev, tests unitaires | `memory://` : générateur synthétique | Personne, pas de MongoDB |
| Dev, test du cycle complet | MongoDB de dev (`mongodb://mongodb:27017/livraison_express`) | L'ETL simulé (`etl_simulator/`), au format de l'ERP |
| Prod | MongoDB des analystes, compte en lecture seule | L'ETL de l'ERP |

- **Le MongoDB et l'ETL de dev** sont deux services du profil `etl` de `docker-compose.dev.yml` (`docker compose -f docker-compose.dev.yml --env-file .env.dev --profile etl up -d --build`). Ils n'existent pas en prod.
- **L'ETL simulé n'utilise pas l'ERP simulé** : `erp_prod_test` joue l'ERP de prod, hors du dépôt, et l'application n'en dépend pas. En prod, `train` joint son MongoDB par son adresse réseau (`TRAINING_SOURCE_URL`), sans réseau Docker partagé : remplacer l'ERP simulé par un vrai serveur ne demande que de changer cette URL. L'ETL simulé écrit directement ce que le vrai ETL chargerait : des commandes au format de l'ERP (`clear`, `suburb`, `business`…), avec un label calculé par une règle métier simulée.
- **Le générateur `memory://` n'a pas les mêmes valeurs que l'ERP** (`normal`, `banlieue`, `premium`…) : un modèle entraîné en `memory://` ne dit rien de son comportement sur les données de l'ERP. Pour tester comme en prod, on passe par le MongoDB de dev.

### Conséquences

- **Implémentation** : `MongoOrderRepository` dans `infrastructure/repository/mongo_order_repository.py`. Elle implémente le même contrat que `InMemoryOrderRepository` (`save`, `get`, `get_training_data`). Dépendance `pymongo`, dans la même version que l'ERP simulé.
- **`save` réservé au dev et à la CI** : il sert à alimenter une base MongoDB de test. En prod, le compte de l'entraînement est en lecture seule et MongoDB refuse l'écriture : seul l'ETL écrit dans la base de l'ERP.
- **Choix par configuration** : la variable `TRAINING_SOURCE_URL` (`memory://` ou `mongodb://hôte:27017/livraison_express`) choisit l'implémentation dans la racine de composition `core/core.py` (`build_order_repository`). En dev, la source reste en mémoire.
- **Validation à la lecture** : MongoDB n'impose aucun schéma. Chaque document est converti en `OrderEntity` : un champ absent, `null` ou de mauvais type écarte le document, compté dans les logs, jamais utilisé en silence. Les documents sans label (`express_eligible`) ne servent pas à l'entraînement.
- **Conversion des dates** : `order_date` est lu en `datetime` et ramené à une date pour choisir les commandes les plus récentes du jeu de test.
- **Comparaison et promotion** (implémentées, voir ADR-0010) : `train` évalue le modèle en service sur le jeu de test du nouveau modèle, et ne remplace le modèle que si le nouveau est meilleur (`PromotionPolicy`). Pour les commandes de l'ERP, le jeu de test est fait des 20 % de commandes arrivées en dernier (`ChronologicalTrainTestSplitter`) : elles sont toujours plus récentes que celles qui ont entraîné le modèle en service.
- **Sécurité, dans la continuité de l'ADR-0007** :
  - un compte MongoDB en lecture seule sur `livraison_express.orders` pour l'entraînement (rôle `read`), créé par l'équipe avec le compte administrateur transmis par l'alternant ;
  - l'authentification MongoDB activée en CI et en prod ;
  - le port MongoDB lié à `127.0.0.1`, et l'accès depuis un poste par tunnel SSH.
- **Tests de contrat** : la même suite vérifie `InMemoryOrderRepository` et `MongoOrderRepository` (`tests/test_order_repository.py`), avec une collection MongoDB factice. Reste à la faire tourner aussi sur un vrai MongoDB, avec un service container en CI.
- **Label ajouté par un labelliseur simulé** : l'ERP simulé (`erp_prod_test`) écrit ses commandes sans label. `etl_simulator`, en mode `label` (`etl_simulator/docker-compose.labeler.yml`), joue le résultat réel des livraisons : il ajoute `express_eligible` aux commandes qui n'en ont pas, avec la règle métier cachée du notebook, sans toucher au reste du document. Le label est tiré à partir de l'`order_id`, donc stable même si l'ERP réécrit une commande. Une commande à laquelle la règle ne s'applique pas (variable à `null`, valeur inconnue) reste sans label, donc hors de l'entraînement. En dev et en test, le mode `generate` écrit des commandes déjà labellisées, comme avant.
- **Passation avant la fin du contrat de l'alternant** : documenter la base (collections, index, sauvegardes, alimentation par l'ERP) et désigner un responsable dans l'équipe.
- **Un historique plus court** : pas de saisonnalité sur plusieurs années. C'est accepté tant que les métriques du modèle restent bonnes.

### Points restant ouverts

- **Source réelle du label** : l'ERP n'envoie aucun label, et ses commandes ne contiennent rien d'où le déduire (ni date ni statut de livraison). Dans la simulation, le labelliseur le remplace (voir « Conséquences ») ; dans une vraie entreprise, il faudra savoir où le SI connaît le résultat réel des livraisons, et qui l'écrit dans MongoDB.
- **Nom du champ du label** : `express_eligible` est supposé, comme la cible du modèle et l'ETL simulé. À confirmer avec l'ERP, sinon changer `LABEL_FIELD` dans `mongo_order_repository.py`.
- **Taille du jeu de test** de la comparaison (20 % des commandes aujourd'hui, ou un nombre de semaines) et **écart minimal** pour qu'un score soit jugé meilleur (`PROMOTION_MIN_GAIN`, 0 aujourd'hui).
- **Récupérer l'historique 2015-2022** si les métriques montrent qu'il manque des données : un export ponctuel en lecture seule depuis PostgreSQL, en heures creuses, vers MongoDB. Il faut pour cela retrouver quelqu'un qui a les droits sur PostgreSQL.
- **Transfert du compte administrateur** de MongoDB à l'équipe : date et modalités, avant la fin du contrat de l'alternant.
- **Sauvegardes de MongoDB** : existent-elles aujourd'hui ? Sinon, un `mongodump` quotidien (ADR-0007).

---

## ADR-0010 — Comment orchestrer le réentraînement du modèle

**Status :** Accepté
**Date :** 29/10/2026

### Contexte

L'ETL de l'ERP ajoute en continu des commandes labellisées dans MongoDB (ADR-0009). Le modèle doit être réentraîné quand assez de nouvelles commandes sont arrivées, avec l'image de prod, puis remplacer le modèle en service seulement s'il est meilleur sur le même jeu de test.

Aujourd'hui, `train` se lance à la main (`docker compose run --rm train`). Il ne se compare à rien et écrase le modèle en service. L'API ne charge le modèle qu'au démarrage : un nouveau modèle n'est servi qu'après un redémarrage.

Contraintes :

- **une seule machine**, sans orchestrateur de conteneurs (ADR-0003) ;
- l'entraînement doit tourner **dans l'image de l'application**, pas dans l'orchestrateur : mêmes dépendances, même code qu'en prod (ADR-0008) ;
- les échecs doivent être visibles et relancés, et chaque exécution doit laisser une trace.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Cron et script sur le serveur | Aucun service en plus | Pas d'interface, pas d'historique, pas de relance. Les conditions (seuil de données, promotion, redémarrage) sont du shell difficile à tester |
| B. Airflow | Standard du MLOps. Interface, historique des exécutions, relances, planification. `DockerOperator` lance l'image de l'application | Lourd : cinq services et une base PostgreSQL de métadonnées. Doit accéder au démon Docker |
| C. Prefect | Plus léger (serveur et worker), flux en Python pur | Moins répandu, moins attendu dans un projet d'industrialisation |
| D. Dagster | Pensé autour des données : recalcule le modèle quand les commandes changent | Logique (« assets ») plus longue à apprendre |

### Décision

**Option B : Airflow**, dans `docker-compose.prod.yml`, à côté de l'application, sur la machine de prod.

**Déclenchement : chaque nuit, et seulement s'il y a assez de nouvelles données.** Le DAG `retrain_express_model` tourne chaque nuit à 2 h. Il n'entraîne que si au moins `RETRAIN_MIN_NEW_ORDERS` commandes labellisées (100 par défaut) sont arrivées depuis le dernier entraînement. Un sensor en continu aurait occupé une place d'exécution en permanence, pour une réactivité inutile : les labels arrivent par lots de l'ETL.

| Tâche | Rôle |
|---|---|
| `enough_new_orders` | Compte les commandes labellisées dans MongoDB et compare au compte du dernier entraînement (variable Airflow `retrain_last_labeled_orders`). Sous le seuil : le reste du DAG est sauté |
| `train` | Lance l'image de prod (`python -m app train`) avec `DockerOperator`, sur le volume du modèle de la prod |
| `read_result` | Lit le résultat de `train`, écrit en JSON sur la dernière ligne de sa sortie |
| `remember_order_count` | Retient le nombre de commandes, pour le seuil de la nuit suivante, que le modèle ait été promu ou non |
| `model_promoted` puis `restart_api` | Redémarre l'API de prod, seulement si le modèle a changé |

**La comparaison est dans l'application, pas dans Airflow.** `train` charge le modèle en service, l'évalue sur le même jeu de test que le nouveau modèle, et ne remplace le modèle que si la métrique `PROMOTION_METRIC` (`f1_score` par défaut) le dépasse d'au moins `PROMOTION_MIN_GAIN` (0 par défaut). Sans modèle en service, le nouveau est toujours promu. Les métriques du modèle en service sont aussi enregistrées dans le run MLflow (`champion_*`). Airflow ne fait qu'enchaîner : la règle se teste avec pytest, sans Airflow.

Raisons :

- **Airflow est le standard** de l'orchestration de pipelines de données et de ML : interface, historique, relances (deux, à cinq minutes d'intervalle) et alertes sans rien écrire.
- **Les tâches lourdes ne tournent pas dans Airflow** : l'image d'Airflow ne contient ni scikit-learn ni le code de l'application, et l'entraînement tourne exactement comme en prod.
- **LocalExecutor** suffit sur une machine : pas de Celery ni de Redis.

### Conséquences

- **Accès à Docker par un proxy** : le socket Docker donne les droits de root sur la machine. Airflow n'y accède qu'à travers `docker-proxy` (`tecnativa/docker-socket-proxy`), qui n'autorise que les conteneurs, les images, le démarrage et le redémarrage. Le proxy n'a pas de port publié.
- **Le conteneur d'entraînement est moins durci** que dans les composes : `DockerOperator` ne permet pas `read_only` ni `cap_drop`. Il tourne quand même avec l'UID 1000, sans droits root.
- **Secrets** : l'URL du MongoDB de l'ERP passe par `private_environment`, jamais affichée dans les logs ni l'interface. Les secrets d'Airflow (base, clé Fernet, JWT) sont dans `.env.prod`, jamais versionné.
- **Interface réservée à l'équipe** : port publié sur `127.0.0.1` uniquement, accès par tunnel SSH (ADR-0007), compte admin du gestionnaire FAB.
- **Le DAG est actif dès son chargement** (`DAGS_ARE_PAUSED_AT_CREATION=false`). Au premier démarrage, Airflow lance aussitôt le run de la dernière nuit passée.
- **Comportement de `train` en dev** : il se compare aussi au modèle existant. Avec les mêmes données synthétiques, le nouveau modèle est identique, donc pas meilleur : le modèle existant est conservé.
- **Coût** : six conteneurs de plus sur la machine de prod (Airflow, sa base et le proxy Docker), qui doit avoir la mémoire nécessaire.
- **Remplacement direct, pour l'instant** : le modèle promu est servi à tout le trafic après le redémarrage de l'API. Le canary de l'ADR-0005 reste à implémenter : le DAG écrira alors le modèle promu à `CANARY_MODEL_PATH`, et il sera d'abord servi à 10 % des commandes.

### Points restant ouverts

- **Seuil** `RETRAIN_MIN_NEW_ORDERS` à ajuster au volume réel des labels de l'ETL.
- **Alertes** en cas d'échec du DAG (e-mail, Slack).
- **Coupure de l'API** de quelques secondes à chaque promotion, le temps du redémarrage. Un rechargement à chaud du modèle la supprimerait.
- **Base de métadonnées** : PostgreSQL dédié à Airflow, qui l'exige. C'est le seul PostgreSQL du système : les données de l'application sont dans MongoDB (ADR-0006).
