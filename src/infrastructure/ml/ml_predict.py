import numpy as np


class MLPredict:
    @staticmethod
    def predict_with_threshold(model, data, threshold=0.5):
        """
        Retourne une prédiction oui/non à partir d'un seuil configurable.
        """
        probabilities = model.predict_proba(data)[:, 1]
        predictions = (probabilities >= threshold).astype(int)

        result = data.copy()
        result["eligibility_probability"] = probabilities.round(4)
        result["express_eligible"] = predictions
        result["decision"] = np.where(
            predictions == 1,
            "oui",
            "non"
        )

        return result
