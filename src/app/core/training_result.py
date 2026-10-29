from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingResult:
    """Résultat d'un entraînement : identifiant du run et métriques."""

    run_id: str
    metrics: dict[str, float]
