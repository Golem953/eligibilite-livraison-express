# livraison-express-lite

Prédiction de l'éligibilité d'une commande à la livraison express.

Une commande est décrite par sa distance, son poids, son montant, la météo, la zone de livraison, le type de client, etc. Un modèle scikit-learn (régression logistique) calcule une probabilité, puis un seuil la transforme en décision « oui » ou « non ». Le modèle est entraîné par une commande en ligne, puis servi par une API FastAPI.

> **Version lite.** Les commandes sont générées en mémoire au démarrage (données synthétiques) et le modèle est un fichier local. Les évolutions prévues (base de données, registre MLflow, Docker, authentification) sont décrites dans [ADR.md](ADR.md).

## Documentation

| Document | Contenu |
|---|---|
| [ARCHITECTURE-livraison-express-lite.md](ARCHITECTURE-livraison-express-lite.md) | Organisation du code, flux de données, pipeline ML, API |
| [ADR.md](ADR.md) | Décisions d'architecture (stockage, MLflow, déploiement, sécurité) |
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
pip install -r requirements.txt
```

`requirements.txt` a été figé sous Windows : il contient `pywin32`, qu'il faut retirer pour installer le projet sous Linux ou macOS.

## Configuration

Copier `.env.example` en `.env`. Une clé laissée vide prend la valeur par défaut définie dans `src/app/config.py`.

| Variable | Défaut | Rôle |
|---|---|---|
| `ENVIRONMENT` | `local` | `local`, `test` ou `prod` |
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

Pour consulter les runs dans le navigateur :

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
│   ├── core.py              assemblage des composants
│   └── learning/            pipeline, entraînement, prédiction, contrat des variables
├── domain/entities.py       commande, prédiction, model card
└── infrastructure/          abstractions de stockage et implémentations de dev
notebooks/                   notebook d'exploration d'origine
order.json                   exemple de commande
```

## Qualité du code

Le linter [Ruff](https://docs.astral.sh/ruff/) est configuré dans `pyproject.toml` :

```powershell
pip install ruff
ruff check .
```

Le projet n'a pas encore de tests automatisés.

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) et le [code de conduite](CODE_OF_CONDUCT.md).

## Licence

Distribué sous licence MIT. Voir [LICENSE](LICENSE).
