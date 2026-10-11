PROJECT_NAME = "eligibilite-livraison-express"
MODEL_VERSION = "1.0.0"
# Version du service (GET /health).
APP_VERSION = "1.0.0"

RANDOM_STATE = 42

# Seuil de décision (cellule 31 du notebook) : à choisir avec le métier.
THRESHOLD = 0.5

# Registre MLflow : nom du modèle et alias de la version servie par l'API.
REGISTERED_MODEL_NAME = PROJECT_NAME
MODEL_ALIAS = "champion"
