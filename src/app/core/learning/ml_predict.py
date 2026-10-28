from datetime import datetime, timezone

from ...config import Settings
from ...domain.entities import OrderEntity, PredictionEntity
from .order_feature import orders_to_dataframe


class MLPredict:
    """
    Effectue une prédiction pour une commande.

    Parameters
    ----------
    model : Pipeline
        Pipeline scikit-learn entraînée.
    threshold : float
        Seuil à partir duquel la commande est considérée comme éligible.
    """
    def __init__(self, model_pipeline, threshold: float | None = None):
        settings = Settings()
        self.threshold = settings.model_threshold if threshold is None else threshold
        self.model_version = settings.model_version
        self.model_pipeline = model_pipeline

    def predict(self, order: OrderEntity) -> PredictionEntity:
        """
    Effectue une prédiction pour une commande.

    Parameters
    ----------
        order : OrderEntity
        Commande à prédire.

    Returns
    -------
    dict
        Résultat de la prédiction.
    """
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
