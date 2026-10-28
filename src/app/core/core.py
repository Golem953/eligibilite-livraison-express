"""Racine de composition : le seul endroit qui connaît les classes concrètes.

Ce module assemble les couches :

```text
abstractions/OrderStore            ← implémenté par → infrastructure/…
abstractions/ModelRepository       ← implémenté par → infrastructure/…
      ↓                                        ↓
application/PredictEligibility  ← reçoit des abstractions, pas des classes
      ↓
api/routers/predictions      ← reçoit les cas d'usage via Depends
```

Conséquence : `api/` n'importent **jamais** la couche des implémentations.
Changer de base de données, c'est modifier ce fichier, et un seul test.
Principe SOLID.
"""
import logging
from datetime import datetime, timezone

from ..config import Settings
from ..domain.entities import ModelEntity
from ..infrastructure.implementation.dev.in_memory_model_repository import FileModelRepository
from ..infrastructure.implementation.dev.in_memory_order_repository import InMemoryOrderRepository
from ..infrastructure.model_repository import ModelRepository
from ..infrastructure.order_repository import OrderRepository
from .learning.ml_pipeline import MLPipeline
from .learning.ml_predict import MLPredict
from .learning.ml_trainer import MLTrainer

logger = logging.getLogger(__name__)


class Core:
    """Assemblage des objets de l'application.

    Une dataclass simple : l'ensemble d'objets devient explicite, lisible en un
    écran, et les tests peuvent en construire un différent de la production.
    """

    _instance = None
    _settings: Settings

    order_repository: OrderRepository
    model_repository: ModelRepository
    model_trainer: MLTrainer
    model_pipeline: MLPipeline
    predict_service: MLPredict

    # Singleton
    def __new__(cls, load_model: bool = False):
        if cls._instance is None:
            cls._instance = super(Core, cls).__new__(cls)
            cls._settings = Settings()
        return cls._instance

    # Constructeur
    def __init__(self, load_model: bool = False):
        """Initialise la classe.

        Ici, on devrait implémenter un Design Pattern **Factory** pour choisir les implémentations.
        Pour faciliter la lecture, l'implémentation est développée en dure.
        """
        if getattr(self, "_initialized", False) and self._load_model == load_model:
            return

        self.configure_logging(self._settings)
        logger.info("Initialisation du contexte d'exécution")

        self.order_repository = InMemoryOrderRepository(generated=True)
        self.model_repository = FileModelRepository(self._settings.model_path)
        if load_model:
            self.model_pipeline = self.model_repository.load(self._settings.model_version)
            if self.model_pipeline is None:
                logger.warning("Aucun modèle disponible pour la prédiction")
            self.model_trainer = None
            self.predict_service = (
                MLPredict(self.model_pipeline) if self.model_pipeline is not None else None
            )
        else:
            self.model_pipeline = MLPipeline().get_model_pipeline()
            self.model_trainer = MLTrainer(self.model_pipeline)
            self.predict_service = MLPredict(self.model_pipeline)
        self._load_model = load_model
        self._initialized = True
        logger.info(
            "Contexte initialisé (load_model=%s, model_path=%s, random_seed=%s)",
            load_model,
            self._settings.model_path,
            self._settings.random_seed,
        )

    def get_settings(self) -> Settings:
        return self._settings

    def get_order_repository(self) -> OrderRepository:
        return self.order_repository

    def get_model_repository(self) -> ModelRepository:
        return self.model_repository

    def get_model_trainer(self) -> MLTrainer | None:
        return self.model_trainer

    def get_model_pipeline(self) -> MLPipeline:
        return self.model_pipeline

    def get_predict_service(self) -> MLPredict | None:
        return self.predict_service

    def train_model(self):
        logger.info("Récupération des données d'entraînement")
        orders, labels = self.order_repository.get_training_data()
        logger.info("Données prêtes (commandes=%d, labels=%d)", len(orders), len(labels))
        run_id, metrics, y_pred, y_proba = self.model_trainer.train(orders, labels)

        model_card = ModelEntity(
            project="livraison-express-lite",
            model_version=self._settings.model_version,
            model_type="LogisticRegression",
            task="classification binaire",
            target="express_eligible",
            threshold=self._settings.model_threshold,
            features=[
                "hour",
                "day_of_week",
                "weekend",
                "distance_km",
                "order_value_eur",
                "weight_kg",
                "stock_available",
                "preparation_time_min",
                "carrier_capacity",
                "weather",
                "delivery_zone",
                "customer_type",
            ],
            metrics=metrics,
            trained_at=datetime.now(timezone.utc),
        )
        self.model_repository.save(self.model_pipeline, model_card)
        logger.info(
            "Modèle sauvegardé au format joblib (path=%s, run_id=%s)",
            self._settings.model_path,
            run_id,
        )
        return run_id, metrics, y_pred, y_proba

    def configure_logging(self, settings: Settings) -> None:
        """On applique le LOG_LEVEL une seule fois."""
        logging.basicConfig(
            level=settings.log_level,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        logger.debug("Logging configuré avec le niveau %s", settings.log_level)
