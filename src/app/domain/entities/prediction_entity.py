from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PredictionEntity:
    """Résultat métier d'une prédiction d'éligibilité."""

    express_eligible: bool
    decision: str
    probability: float
    model_version: str
    prediction_timestamp: str
