"""Règle de promotion : le nouveau modèle remplace-t-il le modèle en service ?"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionPolicy:
    """Promeut le nouveau modèle s'il bat le modèle en service d'au moins `min_gain`.

    Les deux jeux de métriques sont mesurés sur le même jeu de test (ADR-0009). Sans
    modèle en service, le nouveau modèle est toujours promu.
    """

    metric: str = "f1_score"
    min_gain: float = 0.0

    def should_promote(
        self,
        challenger_metrics: dict[str, float],
        champion_metrics: dict[str, float] | None,
    ) -> bool:
        if champion_metrics is None:
            return True
        return challenger_metrics[self.metric] > champion_metrics[self.metric] + self.min_gain
