from datetime import datetime, timezone

from ...domain.entities.order_entity import OrderEntity
from ...domain.entities.prediction_entity import PredictionEntity
from .order_feature import orders_to_dataframe


class MLPredict:
    """Transforme la probabilité du modèle en décision d'éligibilité.

    Parameters
    ----------
    model_pipeline : Pipeline
        Pipeline scikit-learn entraînée.
    threshold : float
        Seuil à partir duquel la commande est considérée comme éligible.
    model_version : str
        Version du modèle, renvoyée avec chaque prédiction.
    """

    def __init__(self, model_pipeline, threshold: float, model_version: str):
        self.model_pipeline = model_pipeline
        self.threshold = threshold
        self.model_version = model_version

    def predict(self, order: OrderEntity) -> PredictionEntity:
        """Prédit l'éligibilité d'une commande."""
        input_df = orders_to_dataframe([order])

        probability = float(self.model_pipeline.predict_proba(input_df)[0, 1])
        eligible = probability >= self.threshold

        return PredictionEntity(
            express_eligible=bool(eligible),
            decision="oui" if eligible else "non",
            probability=round(probability, 4),
            model_version=self.model_version,
            prediction_timestamp=datetime.now(timezone.utc).isoformat(),
        )
