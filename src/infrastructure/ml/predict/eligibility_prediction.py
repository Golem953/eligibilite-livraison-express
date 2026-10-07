"""Fonctions de prédiction reprises du notebook. Écarts : FEATURE_COLUMNS et la
version du modèle sont passés en paramètres (config et registre MLflow), et
datetime.utcnow() (déprécié) est remplacé par datetime.now(UTC)."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd


def predict_with_threshold(model, data, threshold=0.5):
    """
    Retourne une prédiction oui/non à partir d'un seuil configurable.
    """
    probabilities = model.predict_proba(data)[:, 1]
    predictions = (probabilities >= threshold).astype(int)

    result = data.copy()
    result["eligibility_probability"] = probabilities.round(4)
    result["express_eligible"] = predictions
    result["decision"] = np.where(predictions == 1, "oui", "non")

    return result


def predict_order_eligibility(
    order_data, model, feature_columns, model_version, threshold=0.5
):
    """
    Effectue une prédiction pour une commande.

    Parameters
    ----------
    order_data : dict
        Données d'une commande.
    model : Pipeline
        Pipeline scikit-learn entraînée.
    feature_columns : list[str]
        Variables attendues par le modèle.
    model_version : str
        Version du modèle dans le registre MLflow.
    threshold : float
        Seuil à partir duquel la commande est considérée comme éligible.

    Returns
    -------
    dict
        Résultat de la prédiction.
    """
    missing_features = set(feature_columns) - set(order_data.keys())

    if missing_features:
        raise ValueError(f"Variables manquantes : {sorted(missing_features)}")

    input_df = pd.DataFrame(
        [{feature: order_data[feature] for feature in feature_columns}]
    )

    probability = float(model.predict_proba(input_df)[0, 1])
    eligible = probability >= threshold

    return {
        "express_eligible": bool(eligible),
        "decision": "oui" if eligible else "non",
        "probability": round(probability, 4),
        "model_version": model_version,
        "prediction_timestamp": datetime.now(UTC).isoformat(),
    }


def batch_predict_orders(input_df, model, feature_columns, threshold=0.5):
    """
    Réalise une prédiction batch sur plusieurs commandes.
    """
    missing_features = set(feature_columns) - set(input_df.columns)

    if missing_features:
        raise ValueError(
            f"Variables manquantes dans le batch : {sorted(missing_features)}"
        )

    result = input_df.copy()
    result["eligibility_probability"] = model.predict_proba(input_df[feature_columns])[
        :, 1
    ]

    result["express_eligible"] = (
        result["eligibility_probability"] >= threshold
    ).astype(int)

    result["decision"] = np.where(result["express_eligible"] == 1, "oui", "non")

    return result
