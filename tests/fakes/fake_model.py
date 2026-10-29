from __future__ import annotations

import numpy as np


class FakeModel:
    """Modèle factice : renvoie toujours la même probabilité, sans entraînement."""

    def __init__(self, probability: float):
        self.probability = probability

    def predict_proba(self, features):
        return np.array([[1 - self.probability, self.probability]] * len(features))

    def predict(self, features):
        return (self.predict_proba(features)[:, 1] >= 0.5).astype(int)
