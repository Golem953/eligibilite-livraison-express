"""Chargement de training.toml : les paramètres choisis par un humain
(qualité des données, variables, découpage, modèle, évaluation, seuil de
décision, règle du champion)."""

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TRAINING_CONFIG_PATH = Path(__file__).parent / "training.toml"


@dataclass(frozen=True)
class Bounds:
    min: float | None = None
    max: float | None = None


@dataclass(frozen=True)
class QualityConfig:
    required_columns: list[str]
    essential_columns: list[str]
    id_column: str
    date_column: str
    bounds: dict[str, Bounds]
    allowed_values: dict[str, list]


@dataclass(frozen=True)
class FeaturesConfig:
    target_column: str
    numeric_features: list[str]
    categorical_features: list[str]

    @property
    def feature_columns(self) -> list[str]:
        return self.numeric_features + self.categorical_features


@dataclass(frozen=True)
class SplitConfig:
    test_size: float
    random_state: int


@dataclass(frozen=True)
class ModelConfig:
    numeric_imputer_strategy: str
    categorical_imputer_strategy: str
    max_iter: int
    class_weight: str


@dataclass(frozen=True)
class EvaluationConfig:
    metrics: list[str]


@dataclass(frozen=True)
class DecisionConfig:
    threshold: float


@dataclass(frozen=True)
class PromotionConfig:
    metrics: list[str]
    alias: str


@dataclass(frozen=True)
class TrainingConfig:
    quality: QualityConfig
    features: FeaturesConfig
    split: SplitConfig
    model: ModelConfig
    evaluation: EvaluationConfig
    decision: DecisionConfig
    promotion: PromotionConfig


@lru_cache
def get_training_config() -> TrainingConfig:
    with TRAINING_CONFIG_PATH.open("rb") as file:
        raw = tomllib.load(file)
    quality = dict(raw["quality"])
    quality["bounds"] = {
        column: Bounds(**limits) for column, limits in quality["bounds"].items()
    }
    config = TrainingConfig(
        quality=QualityConfig(**quality),
        features=FeaturesConfig(**raw["features"]),
        split=SplitConfig(**raw["split"]),
        model=ModelConfig(**raw["model"]),
        evaluation=EvaluationConfig(**raw["evaluation"]),
        decision=DecisionConfig(**raw["decision"]),
        promotion=PromotionConfig(**raw["promotion"]),
    )
    _check(config)
    return config


def _check(config: TrainingConfig) -> None:
    if not 0 <= config.decision.threshold <= 1:
        raise ValueError("decision.threshold doit être compris entre 0 et 1.")
    if not config.promotion.metrics:
        raise ValueError("promotion.metrics doit contenir au moins un score.")
    unknown = set(config.promotion.metrics) - set(config.evaluation.metrics)
    if unknown:
        raise ValueError(
            f"promotion.metrics {sorted(unknown)} absents de evaluation.metrics."
        )
