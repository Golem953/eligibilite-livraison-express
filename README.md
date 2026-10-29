# livraison-express-lite

Prédiction de l'éligibilité d'une commande à la livraison express.

Une commande est décrite par sa distance, son poids, son montant, la météo, la zone de livraison, le type de client, etc. Un modèle scikit-learn (régression logistique) calcule une probabilité, puis un seuil la transforme en décision « oui » ou « non ». Le modèle est entraîné par une commande en ligne, puis servi par une API FastAPI.

> **Version lite.** Les commandes sont générées en mémoire au démarrage (données synthétiques) et le modèle est un fichier local. Les évolutions prévues (base de données, registre MLflow, Docker, authentification) sont décrites dans [ADR.md](ADR.md).

## Documentation

| Document | Contenu |
|---|---|
| [ARCHITECTURE-livraison-express-lite.md](ARCHITECTURE-livraison-express-lite.md) | Organisation du code, flux de données, pipeline ML, API |
| [ADR.md](ADR.md) | Décisions d'architecture (stockage, MLflow, déploiement, sécurité, source des données) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branches, commits, revue de code |
| [SECURITY.md](SECURITY.md) | Signaler une vulnérabilité |

## Prérequis

- Python **3.13**
- Git

## Installation

```powershell
git clone https://github.com/Golem953/eligibilite-livraison-express.git
cd eligibilite-livraison-express

python -m venv .venv
.venv\Scripts\activate               # Linux / macOS : source .venv/bin/activate
pip install -r requirements-dev.txt
```

| Fichier | Contenu | Usage |
|---|---|---|
| `requirements.txt` | Ce dont l'application a besoin pour tourner, versions figées | Images Docker `test` et `prod` |
| `requirements-dev.txt` | `requirements.txt` + pytest, ruff et le MLflow complet (pour `mlflow ui`) | Poste de développement, image `dev` |

## Configuration

Copier `.env.example` en `.env`. Une clé laissée vide prend la valeur par défaut définie dans `src/app/config.py`.

| Variable | Défaut | Rôle |
|---|---|---|
| `MODEL_PATH` | `notebooks/artifacts/express_delivery_model.joblib` | Fichier du modèle écrit par `train` et lu par l'API |
| `MODEL_THRESHOLD` | `0.5` | Seuil de probabilité au-delà duquel la commande est éligible |
| `MODEL_VERSION` | `1.0.0` | Version renvoyée dans chaque prédiction |
| `RANDOM_SEED` | `42` | Graine de la génération des données et de l'entraînement |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` ou `ERROR` |

### MLflow

Chaque entraînement est enregistré dans MLflow. MLflow ne lit pas le fichier `.env` : ses variables se définissent dans le terminal, **avant** de lancer `train`.

```powershell
$env:MLFLOW_TRACKING_URI = "./mlruns"
$env:MLFLOW_ALLOW_FILE_STORE = "true"
```

Sous Linux / macOS : `export MLFLOW_TRACKING_URI=./mlruns MLFLOW_ALLOW_FILE_STORE=true`.

- Les runs sont alors écrits dans le dossier `mlruns/`, exclu de git.
- Sans `MLFLOW_TRACKING_URI`, MLflow crée une base SQLite `mlflow.db` dans le dossier courant.
- Sans `MLFLOW_ALLOW_FILE_STORE=true`, MLflow refuse le stockage dans `mlruns/`.

Pour consulter les runs dans le navigateur (MLflow complet, installé par `requirements-dev.txt`) :

```powershell
mlflow ui --backend-store-uri ./mlruns
```

Puis ouvrir http://127.0.0.1:5000.

## Utilisation

Toutes les commandes se lancent **depuis la racine du dépôt**, environnement virtuel activé.

### 1. Entraîner le modèle

```powershell
python -m src.app train
```

L'entraînement génère 6000 commandes synthétiques, entraîne le pipeline (split 80/20 stratifié), enregistre un run MLflow, puis écrit trois fichiers dans le dossier de `MODEL_PATH` :

- `express_delivery_model.joblib` : le pipeline entraîné ;
- `metrics.json` : accuracy, precision, recall, f1, ROC AUC ;
- `features.json` : la liste et l'ordre des variables.

Chaque entraînement remplace les fichiers précédents. La commande renvoie le code 0 en cas de succès, 1 en cas d'échec.

### 2. Prédire une commande sans serveur

```powershell
python -m src.app predict --file order.json
```

```json
{
  "express_eligible": true,
  "decision": "oui",
  "probability": 0.9377,
  "model_version": "1.0.0",
  "prediction_timestamp": "2026-10-26T13:29:04.016464+00:00"
}
```

### 3. Démarrer l'API

```powershell
python -m src.app serve                # http://127.0.0.1:8000
python -m src.app serve --port 8080
```

L'API charge le modèle une seule fois au démarrage. Après un nouvel entraînement, il faut la redémarrer pour servir le nouveau modèle. Si aucun modèle n'existe, elle démarre quand même et répond 503 sur `/health/ready` et `/predict`.

La documentation interactive est disponible sur http://127.0.0.1:8000/docs.

## Routes de l'API

| Route | Rôle | Réponses |
|---|---|---|
| `GET /health` | Le processus est vivant | 200 |
| `GET /health/ready` | Le modèle est chargé | 200, ou 503 si aucun modèle |
| `POST /predict` | Prédit l'éligibilité d'une commande | 200, 422 si la commande est invalide, 503 si aucun modèle |

Exemple d'appel avec le fichier `order.json` du dépôt :

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/predict `
  -ContentType "application/json" -InFile order.json
```

```bash
curl -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" -d @order.json
```

### Format d'une commande

| Champ | Type | Exemple |
|---|---|---|
| `hour` | entier, heure de la commande | `14` |
| `day_of_week` | entier, 0 = lundi | `2` |
| `weekend` | 0 ou 1 | `0` |
| `distance_km` | décimal | `3.5` |
| `order_value_eur` | décimal | `89.9` |
| `weight_kg` | décimal | `2.4` |
| `stock_available` | 0 ou 1 | `1` |
| `preparation_time_min` | décimal | `18` |
| `carrier_capacity` | décimal entre 0 et 1 | `0.85` |
| `weather` | `normal`, `pluie`, `neige` ou `orage` | `"normal"` |
| `delivery_zone` | `centre`, `proche_banlieue`, `banlieue` ou `rurale` | `"centre"` |
| `customer_type` | `standard` ou `premium` | `"premium"` |
| `order_id` | texte, facultatif | `"CMD-0001"` |

`order_id` identifie la commande mais n'est pas utilisé par le modèle.

## Structure du dépôt

```text
src/app/
├── __main__.py              point d'entrée python -m
├── cli.py                   commandes serve, train, predict
├── config.py                configuration lue depuis l'environnement et .env
├── api/app.py               API FastAPI
├── core/
│   ├── core.py              racine de composition : assemble l'API et l'entraînement
│   ├── training_service.py  cas d'usage « entraîner le modèle »
│   ├── training_result.py   résultat d'un entraînement
│   └── learning/            pipeline, entraînement, prédiction, contrat des variables
├── domain/
│   ├── entities/            commande, prédiction, model card (un fichier par classe)
│   └── interface/           interfaces (ABC) : *_interface.py
└── infrastructure/
    ├── repository/          implémentations des repositories : mémoire, fichier
    └── implementation/      MLflow, générateur de données de dev
notebooks/                   notebook d'exploration d'origine
order.json                   exemple de commande
tests/                       tests pytest
.github/workflows/           CI (ci.yml) et CD (cd.yml)
```

## Qualité du code

Le linter [Ruff](https://docs.astral.sh/ruff/) et les tests [pytest](https://docs.pytest.org/) sont installés par `requirements-dev.txt` :

```powershell
ruff check .
pytest
```

| Tests | Ce qu'ils vérifient |
|---|---|
| `test_order_feature.py` | Le contrat des variables du modèle : mêmes colonnes, même ordre, `order_id` exclu |
| `test_order_generator.py` | Le générateur de données : reproductible, labels binaires, identifiants uniques |
| `test_ml_predict.py` | La décision selon le seuil, l'arrondi de la probabilité, la version et l'horodatage |
| `test_api.py` | Les routes, les statuts 200/503/422, le contrat de réponse de `/predict`, et l'isolation de l'API (elle n'importe ni MLflow ni le code d'entraînement) |
| `test_training.py` | L'entraînement et ses métriques, le service d'entraînement, les stockages du modèle et des commandes, puis l'assemblage complet de bout en bout |

Les classes reçoivent leurs dépendances au lieu de les créer : les tests leur passent un modèle ou un tracker MLflow factice. Ils sont rapides et ne dépendent pas d'un entraînement préalable.

## CI/CD

GitHub Actions lance la CI (Ruff, pytest, build de l'image) à chaque push et pull request sur `dev`. La fusion d'une release dans `main` publie l'image de production sur GitHub Container Registry, sans la déployer. Le détail est dans [CONTRIBUTING.md](CONTRIBUTING.md#cicd).

## Image Docker : optimisation et sécurité

Les commandes de lancement par environnement sont dans [CONTRIBUTING.md](CONTRIBUTING.md#images-docker).

### Optimisation

| Mesure | Effet |
|---|---|
| Image de base `python:3.13-slim` | Debian minimale, sans compilateurs ni outils superflus |
| Build multi-étapes (`dev`, `test`, `prod`) | Les images `test` et `prod` ne contiennent ni les tests, ni les outils de développement, ni la documentation |
| `requirements.txt` limité à ce que le code importe | 55 paquets au lieu de 94 : `mlflow-skinny` remplace le MLflow complet (sans serveur Flask, `pyarrow`, `matplotlib`, `sqlalchemy`…) |
| Dépendances installées avant la copie du code | Une modification du code ne relance pas `pip install`, qui reste en cache |
| `PIP_NO_CACHE_DIR`, `PYTHONDONTWRITEBYTECODE` | Ni cache pip, ni fichiers `.pyc` dans l'image |
| `.dockerignore` | `.git`, `.venv`, notebooks, modèles et secrets n'entrent pas dans le contexte de build |

Image `prod` mesurée avant et après la réduction des dépendances :

| | Avant | Après |
|---|---|---|
| Taille sur disque | 1,26 Go | 790 Mo (−37 %) |
| Taille compressée (téléchargée depuis un registre) | 272 Mo | 168 Mo (−38 %) |
| Paquets Python | 94 | 55 |

L'essentiel de ce qui reste vient de `scipy`, `pandas`, `scikit-learn` et `numpy`, indispensables au modèle.

### Sécurité

**Dans l'image (`Dockerfile`) :**

- **Utilisateur non-root** `appuser` (UID 1000, sans dossier personnel ni shell de connexion) dans `test` et `prod`.
- **Code en lecture seule pour l'application** : il est copié par root, avant le passage à `appuser`.
- **pip retiré** des images `test` et `prod` : il n'y sert plus, et embarque ses propres copies vulnérables d'`urllib3` et `msgpack`.
- **Image de base figée** par version exacte et empreinte (`python:3.13.18-slim@sha256:…`) : deux builds produisent la même image.
- **Aucun secret** : `.env` est exclu par `.dockerignore`, aucun mot de passe dans `ENV`.

**Au lancement (`docker-compose.yml`), pour tous les services :**

- **Système de fichiers en lecture seule** (`read_only`) : seuls le volume `/data` et `/tmp` sont modifiables.
- **Aucune capacité Linux** (`cap_drop: ALL`) ; `init-volume` ne récupère que `CHOWN`.
- **Pas d'élévation de privilèges** (`no-new-privileges`).
- **Ports publiés uniquement sur `127.0.0.1`**.
- **MLflow lancé avec l'UID 1000**, alors que son image officielle tourne en root par défaut.

**Analyse des vulnérabilités** avec [Trivy](https://trivy.dev/), image `prod` :

| | Avant | Après |
|---|---|---|
| Paquets Python | 8 (dont 5 HIGH) | 0 |
| Paquets Debian de l'image de base | 164 (dont 44 HIGH) | 164 (dont 44 HIGH) |
| CRITICAL | 0 | 0 |

Les vulnérabilités restantes concernent des paquets Debian (`util-linux`, `systemd`, `ncurses`, `perl`) pour lesquels aucun correctif n'est encore publié. Elles disparaîtront en mettant à jour la version figée de l'image de base quand Debian les corrigera.

Pour relancer l'analyse :

```powershell
docker build --target prod -t livraison-express:prod .
docker image save livraison-express:prod -o image.tar
docker run --rm -v "${PWD}:/scan" aquasec/trivy:0.58.1 image --input /scan/image.tar --scanners vuln --severity HIGH,CRITICAL
```

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) et le [code de conduite](CODE_OF_CONDUCT.md).

## Licence

Distribué sous licence MIT. Voir [LICENSE](LICENSE).
