from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Prediction:
    """Résultat du modèle pour une commande.

    Ce n'est pas un label : la vérité terrain est le label réel, remonté plus tard
    (ADR-0001).
    """

    eligible: bool
    probability: float
    model_version: str
    predicted_at: datetime

    def __post_init__(self) -> None:
        if not 0 <= self.probability <= 1:
            raise ValueError("probability doit être comprise entre 0 et 1.")
