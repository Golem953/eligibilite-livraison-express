from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingResult:
    """Résultat d'un entraînement.

    `metrics` : nouveau modèle ; `champion_metrics` : modèle en service, mesuré sur le
    même jeu de test (`None` s'il n'y en avait pas) ; `promoted` : le nouveau modèle a
    remplacé le modèle en service.
    """

    run_id: str
    metrics: dict[str, float]
    champion_metrics: dict[str, float] | None = None
    promoted: bool = True
