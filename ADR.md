# Architecture Decision Records

Enregistrement des décisions d'architecture du projet **eligibilite-livraison-express**.

| ADR | Titre | Statut |
|---|---|---|
| [ADR-0001](#adr-0001--où-stocker-les-commandes-reçues-par-lapi) | Où stocker les commandes reçues par l'API | Accepté |
| [ADR-0002](#adr-0002--où-stocker-les-artéfacts-du-modèle-de-machine-learning) | Où stocker les artéfacts du modèle de Machine Learning | Accepté |
| [ADR-0003](#adr-0003--où-et-comment-exécuter-lentraînement-du-modèle) | Où et comment exécuter l'entraînement du modèle | Accepté |

---

## ADR-0001 — Où stocker les commandes reçues par l'API

**Status :** Accepté
**Date :** 06/10/2026

### Contexte

L'API reçoit de nouvelles commandes et prédit leur éligibilité à la livraison express.
Chaque commande doit être conservée avec sa prédiction, pour servir plus tard au réentraînement du modèle.

Ce que le stockage doit permettre :

- **Écrire une ligne à chaque appel de l'API.** Les écritures sont fréquentes et unitaires. Elles peuvent être concurrentes si l'API tourne avec plusieurs workers.
- **Conserver la prédiction et la version du modèle** qui l'a produite, pour l'audit et le monitoring.
- **Compléter la commande plus tard avec le résultat réel** (la livraison express était-elle vraiment possible ?). Sans ce label, la commande ne sert pas au réentraînement. Il faut donc pouvoir **mettre à jour** ou **joindre** des données après coup.
- **Extraire un jeu d'entraînement** (commandes labellisées sur une période donnée) que le pipeline de réentraînement charge dans pandas.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. SQLite | Un seul fichier, SQL disponible, aucun service | Un seul écrivain à la fois, inutilisable si l'API et l'entraînement tournent sur deux machines |
| B. PostgreSQL (conteneur docker-compose) | Écritures concurrentes, mises à jour et jointures faciles, standard en production, type `JSONB`, backend MLflow bien supporté (base mutualisable avec l'ADR-0002) | Service supplémentaire à maintenir (configuration, sauvegardes, migrations) |
| C. MariaDB (conteneur docker-compose) | Écritures concurrentes, mises à jour et jointures faciles, prise en main simple si l'équipe connaît MySQL | Service supplémentaire à maintenir, support JSON moins riche que PostgreSQL, backend MLflow moins courant |
| D. SQLite en dev, PostgreSQL en CI et en prod | Dev léger et instantané (aucun service, aucun Docker), robustesse de PostgreSQL là où ça compte | SQLite est moins strict que PostgreSQL : des erreurs peuvent passer en dev, à compenser par la CI |

### Décision

**Option D : SQLite en développement, PostgreSQL en test (CI) et en production.**

- **En dev, SQLite** : léger, démarrage instantané, rien à installer. L'objectif est l'environnement de développement le plus rapide possible pour les futurs collaborateurs.
- **En CI et en prod, PostgreSQL** : écritures concurrentes et typage strict.
- **En contrepartie de la souplesse de SQLite**, la CI comporte de nombreux tests qui vérifient que le code respecte les mêmes contrôles que PostgreSQL, voire davantage.
- **Le code doit fonctionner avec n'importe quel moteur de base de données.** Il ne dépend d'aucune fonctionnalité propre à un SGBD.

### Conséquences

- **Flux de `POST /predict` (implémenté)** : le modèle champion prédit d'abord, puis la commande est enregistrée directement au statut « prédite » en une seule écriture. Sans modèle disponible, rien n'est enregistré (réponse 503), ce qui évite des commandes « reçues » orphelines et des doublons d'identifiant quand le client réessaie.
- **Commandes historiques** : une commande peut être au statut « labellisée » sans avoir de prédiction (commande antérieure au modèle, par exemple les données d'amorçage). Le statut « labellisée » exige le label réel ; la prédiction y est soit complète, soit totalement absente.
- **Choix du moteur par configuration** : l'URL de connexion (`DATABASE_URL`) détermine le moteur. Le choix de l'adapter se fait uniquement dans la composition root (`dependency_injection`).
- **Code agnostique du moteur** : aucune fonctionnalité spécifique à un SGBD (`JSONB`, syntaxes d'upsert propres à un moteur, fonctions de date spécifiques). L'argument « `JSONB` » de PostgreSQL est donc abandonné. Accès SQL par **pilotes natifs** (`sqlite3`, `psycopg`) derrière une interface `DatabaseConnectorInterface` (une implémentation par moteur, choisie dans la composition root). Les requêtes utilisent une convention unique de paramètres nommés `:nom`, que chaque connecteur traduit pour son pilote. Pas d'ORM ni d'Alembic : un script de création de schéma par moteur.
- **Contrôles portés par le schéma et le code, pas par le moteur** : contraintes déclarées explicitement (`NOT NULL`, `CHECK`, `UNIQUE`, clés étrangères) et validation des données côté domaine/API avant l'écriture.
- **SQLite configuré au maximum de sa rigueur** (voir ci-dessous).
- **CI renforcée** : la même suite de tests d'intégration du repository tourne sur SQLite **et** sur PostgreSQL (service container GitHub Actions). Un test qui passe sur l'un et échoue sur l'autre bloque le pipeline.
- **Déploiement** : un serveur PostgreSQL fonctionne que l'API et le réentraînement tournent sur une ou deux machines. La question n'influence plus le choix du moteur.
- **Outillage** : DBeaver pour consulter les données, aussi bien la base SQLite de dev que PostgreSQL.
- **Architecture** : l'accès aux commandes passe par un port `outbound/order_repository_interface.py`. Changer de moteur revient à changer la configuration, voire à écrire un nouvel adapter, sans toucher au métier ni aux routes.

#### Configuration stricte de SQLite (obligatoire)

SQLite doit appliquer les règles **au moins aussi strictement que PostgreSQL**. Les réglages suivants sont obligatoires, pas optionnels :

| Règle | Comportement par défaut de SQLite | Mesure imposée |
|---|---|---|
| Clés étrangères | Ignorées | `PRAGMA foreign_keys = ON` à **chaque connexion** (le réglage n'est pas persistant) |
| Typage des colonnes | Permissif : on peut mettre du texte dans une colonne `INTEGER` | Toutes les tables en mode **`STRICT`** (SQLite ≥ 3.37) |
| Type `ANY` | Accepte n'importe quelle valeur même en `STRICT` | Interdit |
| Longueur des chaînes | `VARCHAR(50)` n'est pas vérifié | `CHECK (length(colonne) <= 50)` |
| Booléens | Pas de type booléen, n'importe quel entier est accepté | Colonne `INTEGER` + `CHECK (colonne IN (0, 1))` |
| Dates | Pas de type date, n'importe quel texte est accepté | Colonne `TEXT` au format ISO 8601 + `CHECK` sur le format |
| Valeurs énumérées (statut, etc.) | Aucun contrôle | `CHECK (statut IN ('recue', 'predite', 'labellisee'))` |
| Contraintes `CHECK` | Actives | `PRAGMA ignore_check_constraints = OFF` explicite |

Conséquences de ce choix :

- **Les types diffèrent entre SQLite et PostgreSQL** : une table `STRICT` n'accepte que `INTEGER`, `REAL`, `TEXT`, `BLOB` et `ANY`. Les types `BOOLEAN`, `TIMESTAMP` ou `VARCHAR` sont donc traduits côté SQLite (`INTEGER` + `CHECK`, `TEXT` ISO 8601 en UTC + `CHECK`). D'où un script de schéma par moteur, avec les mêmes contraintes des deux côtés.
- **Des tests vérifient la configuration elle-même** : au démarrage d'une connexion SQLite, on contrôle que `foreign_keys` vaut `1` et que chaque table est bien `STRICT`. Un test insère volontairement des données invalides (mauvais type, clé étrangère orpheline, statut inconnu, chaîne trop longue) et vérifie qu'elles sont **rejetées sur les deux moteurs**.
- **Limites résiduelles**, couvertes par les tests sur PostgreSQL en CI : SQLite accepte certaines syntaxes laxistes (par exemple une chaîne entre guillemets doubles `"..."` traitée comme un littéral) et son `LIKE` ignore la casse, contrairement à PostgreSQL.

### Points restant ouverts (sans impact sur le choix du moteur)

- Quel **volume** de commandes viser (par jour, au total) ?
- Comment et quand le **label réel** remonte-t-il (par l'API, par un import batch, par simulation) ?

---

## ADR-0002 — Où stocker les artéfacts du modèle de Machine Learning

**Status :** Accepté
**Date :** 06/10/2026

### Contexte

L'outil d'entraînement (ADR-0003) produit régulièrement de nouvelles versions du modèle (pipeline scikit-learn sérialisé), réentraînées sur les commandes labellisées (ADR-0001). L'API doit charger la version en production pour prédire.

Ce que le stockage doit permettre :

- **Écrire une nouvelle version** du modèle à chaque entraînement, avec ses métriques et ses hyperparamètres.
- **Charger la version en production** au démarrage de l'API.
- **Tracer chaque prédiction** : la version du modèle enregistrée avec chaque commande (ADR-0001) doit permettre de retrouver le modèle exact qui l'a produite.
- **Revenir en arrière** vers une version précédente si un nouveau modèle se dégrade.
- **Suivre l'évolution** des modèles : savoir quelle version tourne et comment ses performances évoluent d'un entraînement à l'autre.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Modèle intégré à l'image Docker (`model.joblib` copié au build) | Très simple, l'image et le modèle sont versionnés ensemble | Chaque réentraînement impose un rebuild et un redéploiement. Binaire dans git (ou git LFS). Aucune métrique associée |
| B. Volume partagé docker-compose (`models/<version>/model.joblib` + `metadata.json` + pointeur vers la version courante) | Aucun service supplémentaire : l'entraînement écrit, l'API lit | Versioning et métadonnées faits maison. Une seule machine. Aucune interface |
| C. MLflow Tracking + Model Registry (conteneur serveur MLflow) | Versions, métriques, paramètres et lien vers le run d'entraînement. Alias pour désigner la version en production. Interface web. Retour arrière simple. Déjà dans les dépendances | Un service de plus. L'API dépend du serveur MLflow au démarrage. Courbe d'apprentissage |

### Décision

**Option C : MLflow Tracking + Model Registry.**

- **Simplicité d'utilisation** : le registre et l'interface web évitent de réinventer le versioning, les métadonnées et le retour arrière.
- **Métriques au service de la production** : chaque entraînement enregistre ses métriques, qui servent à juger si une version mérite de passer en production.
- **Visibilité** : savoir à tout moment quelle version tourne et où en sont les performances.
- **Apprentissage** : MLflow est un outil standard du MLOps. La courbe d'apprentissage est acceptée, et même recherchée.

**Backend store de MLflow (métadonnées et Model Registry) : une base dédiée, séparée de celle des commandes, sur le même moteur que l'ADR-0001.**

| Environnement | Base des commandes (ADR-0001) | Backend store MLflow |
|---|---|---|
| Dev | Fichier SQLite `commandes.db` | Fichier SQLite `mlflow.db` |
| CI / Prod | Base `commandes` | Base `mlflow`, **dans le même conteneur PostgreSQL** |

- **Séparer les bases** évite que les tables de MLflow et les nôtres se mélangent (collisions de noms, table `alembic_version` partagée si nos migrations utilisent aussi Alembic). Chaque base garde ses propres migrations et sauvegardes.
- **Un seul conteneur PostgreSQL** suffit : pas de second serveur à maintenir.
- **En SQLite, deux fichiers distincts** : SQLite n'accepte qu'un écrivain à la fois par fichier, donc un entraînement qui écrit dans MLflow ne bloque pas l'API qui enregistre une commande.

**Artifact store (fichiers du modèle) : un volume Docker monté sur le conteneur MLflow.**

- Les fichiers des modèles (`model.pkl`, `MLmodel`, `requirements.txt`…) sont écrits dans un dossier du conteneur MLflow (par exemple `/mlflow/mlartifacts`), monté sur un volume Docker. Ils survivent à la suppression et à la recréation du conteneur.
- Le serveur MLflow sert d'intermédiaire : L'outil d'entraînement et l'API envoient et récupèrent les fichiers par son API HTTP. Seul le conteneur MLflow monte le volume.

**Droits d'accès : un utilisateur PostgreSQL par base.**

| Utilisateur | Base | Utilisé par |
|---|---|---|
| `commandes_user` | `commandes` | l'API et l'outil d'entraînement |
| `mlflow_user` | `mlflow` | le serveur MLflow uniquement |

Aucun service ne peut modifier la base d'un autre.

### Conséquences

- **Nouveau service** : un conteneur serveur MLflow (`ghcr.io/mlflow/mlflow`, même version que le client) s'ajoute au docker-compose, aux côtés de l'API et de la base. Il est lancé avec `--allowed-hosts`, sans quoi il refuse les appels de l'API vers `mlflow:5000`.
- **État actuel de l'implémentation** : le backend store est pour l'instant un fichier SQLite dans le volume du serveur MLflow, quel que soit l'environnement ; la base `mlflow` de PostgreSQL et son utilisateur restent à mettre en place (variable `MLFLOW_BACKEND_STORE_URI`, pilote PostgreSQL à ajouter à l'image MLflow). Hors Docker, le client utilise `sqlite:///data/mlflow.db`.
- **Promotion automatique du champion** (décidé le 07/10/2026) : après chaque entraînement, la nouvelle version reçoit l'alias `champion` si elle bat le champion actuel, ou s'il n'y a pas encore de champion. Les scores de référence sont une liste ordonnée dans `infrastructure/config/training.toml` (`[promotion].metrics`, parmi `[evaluation].metrics`) : le premier décide, les suivants départagent les égalités ; égalité sur tous : le champion est conservé. Les scores comparés sont calculés sur des jeux de test différents d'un entraînement à l'autre.
- **Format des modèles** : MLflow 3 enregistre les modèles scikit-learn au format skops, qui n'accepte au rechargement que les types déclarés sûrs (`skops_trusted_types`).
- **Initialisation de PostgreSQL** : un script exécuté au premier démarrage du conteneur crée les deux bases (`commandes`, `mlflow`) et leurs utilisateurs, chacun propriétaire de sa base uniquement.
- **Secrets** : deux couples identifiant / mot de passe à fournir par variables d'environnement (`.env`, non versionné), un par base.
- **Volume des artéfacts** : lié à la machine hôte. Sa sauvegarde est à prévoir explicitement. En cas de passage à plusieurs machines, l'artifact store pourra migrer vers un stockage S3-compatible (MinIO) en changeant uniquement la configuration du serveur MLflow, sans toucher au code de l'API ni de l'outil d'entraînement.
- **Schéma géré par MLflow** : MLflow crée et fait évoluer ses propres tables (`mlflow db upgrade`). Les règles de rigueur imposées à SQLite par l'ADR-0001 (tables `STRICT`, `CHECK`…) s'appliquent à nos tables, pas à celles de MLflow.
- **Chaque entraînement est un run MLflow** : paramètres, métriques et modèle y sont enregistrés. Le modèle est inscrit dans le Model Registry sous un nom unique, et la version en production est désignée par un alias.
- **Traçabilité avec l'ADR-0001** : la version du modèle stockée avec chaque prédiction correspond à la version du Model Registry.
- **Dépendance au démarrage** : l'API charge le modèle **une seule fois au démarrage** et le garde en mémoire. Elle ne sollicite pas MLflow à chaque prédiction.
- **Architecture** : l'accès au modèle passe par un port `outbound/model_repository_interface.py`, implémenté par un adapter `MlflowModelRepository`. L'API et le métier ne dépendent pas directement de MLflow, et un autre adapter (par exemple sur fichiers locaux pour les tests) reste possible.

### Points restant ouverts

- **Artifact store en dev** (sans Docker) : simple dossier local, par cohérence avec le « dev léger » de l'ADR-0001 ?
- **Prise en compte d'un nouveau modèle par l'API** : au redémarrage, via une route de rechargement, ou par vérification périodique ?
- **Reproductibilité des données** : enregistrer dans le run la période ou une empreinte du jeu d'entraînement extrait de la base ?
- **Interface MLflow** : publiée pour l'instant sur le port 8059. À confirmer, et à protéger si le port reste ouvert sur le réseau.

---

## ADR-0003 — Où et comment exécuter l'entraînement du modèle

**Status :** Accepté
**Date :** 06/10/2026

### Contexte

Tout le travail de Machine Learning se trouve aujourd'hui dans un notebook d'exploration, en dehors du dépôt : génération de données fictives, contrôles qualité, nettoyage, sélection des variables, construction du pipeline scikit-learn, entraînement suivi par MLflow, évaluation, choix du seuil.

Pour industrialiser, l'entraînement doit :

- **Lire les commandes labellisées** dans la base (ADR-0001).
- **Enregistrer chaque nouvelle version** du modèle dans MLflow (ADR-0002).
- **Partager le même code** que la prédiction pour la validation des commandes et la préparation des variables. Sinon le modèle reçoit en production des données préparées différemment de celles sur lesquelles il a appris.
- **Ne pas dégrader l'API** : un entraînement est long et consomme du CPU, alors que l'API doit rester disponible et rapide.

### Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Entraînement exécuté dans l'API (une route qui entraîne dans le processus de l'API) | Un seul programme, déclenchable par HTTP | Ralentit les prédictions pendant l'entraînement. Un plantage de l'entraînement fait tomber l'API |
| B. Outil en ligne de commande dans le même dépôt, exécuté dans un processus séparé | Code partagé avec l'API, donc toujours synchronisé. API non impactée. Déclenchable par un humain, un cron ou la CI | Un point d'entrée supplémentaire à maintenir |
| C. Projet séparé, dans un autre dépôt | Isolation totale | Code partagé dupliqué ou à publier en bibliothèque. Risque de désynchronisation entre l'entraînement et la prédiction |
| D. Entraînement manuel depuis le notebook | Rien à développer | Non reproductible, non automatisable : contraire à l'objectif d'industrialisation |

### Décision

**Option B : l'entraînement est un outil en ligne de commande, dans le même dépôt que l'API, exécuté dans un processus séparé.**

- **Même dépôt, même `src/`** : l'API et l'outil partagent le domaine (la commande et ses règles de validité), les ports et les repositories. Une évolution du modèle (nouvelle variable, par exemple) modifie l'entraînement et la prédiction dans le même commit.
- **Deux points d'entrée distincts** : l'API est un service qui tourne en permanence ; l'outil d'entraînement est lancé, fait son travail, puis s'arrête.
- **Isolation** : l'API n'importe jamais le code d'entraînement, et l'outil d'entraînement n'importe jamais FastAPI.
- **Déclenchement par l'API** : la route `POST /train` démarre l'outil d'entraînement dans un **processus séparé** (`python -m infrastructure.adapter.cli.train`) et répond immédiatement (202). Un seul entraînement à la fois (409 sinon). L'outil reste utilisable à la main avec la même commande.

### Conséquences

- **Architecture** : l'entraînement est un use case de la couche `application`, appelé par un adapter d'entrée en ligne de commande (`infrastructure/adapter/cli/`), comme l'API est un adapter d'entrée HTTP. Il dépend uniquement de ports (`OrderRepositoryInterface`, `ModelRepositoryInterface`, et un port d'entraînement), sans connaître directement SQL, scikit-learn ni MLflow.
- **Migration du notebook** : le code utile du notebook est extrait vers `src/`. La génération de données fictives n'est pas du code de production ; elle va dans les fixtures de test ou dans un script d'alimentation de la base de dev. L'exploration et les graphiques restent dans le notebook.
- **Préparation des variables dans le pipeline** : le nettoyage et la préparation des variables sont intégrés autant que possible au pipeline scikit-learn enregistré dans MLflow, pour garantir un traitement identique à l'entraînement et à la prédiction.
- **Autres outils possibles** sur le même modèle : calcul des métriques réelles en production, promotion d'une version, alimentation de la base de dev.

### Points restant ouverts

- **Déclenchement automatique** : en plus de la route `/train` et de la commande manuelle, faut-il un déclenchement planifié (cron), sur condition de données, sur dégradation des métriques, ou par la CI ?
- **Image Docker** : de fait une seule image, puisque `/train` lance l'entraînement dans le conteneur de l'API. À confirmer.
- **Sécurité de `/train`** : la route n'est pas authentifiée alors que le port 8057 est publié sur le réseau.
- **Rechargement du modèle par l'API** (repris de l'ADR-0002) : au redémarrage, via une route, ou par vérification périodique de l'alias `champion` ?
- **Structure détaillée de `src/`** pour l'entraînement : à valider au moment de l'implémentation.
