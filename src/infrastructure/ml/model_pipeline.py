"""Construction de la pipeline de machine learning (repris du notebook)."""

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from infrastructure.config.training_config import TrainingConfig


def build_model_pipeline(config: TrainingConfig) -> Pipeline:
    NUMERIC_FEATURES = config.features.numeric_features
    CATEGORICAL_FEATURES = config.features.categorical_features
    RANDOM_STATE = config.split.random_state

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy=config.model.numeric_imputer_strategy)),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy=config.model.categorical_imputer_strategy),
            ),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", numeric_transformer, NUMERIC_FEATURES),
            ("categorical", categorical_transformer, CATEGORICAL_FEATURES),
        ]
    )

    classifier = LogisticRegression(
        max_iter=config.model.max_iter,
        class_weight=config.model.class_weight,
        random_state=RANDOM_STATE,
    )

    model_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )

    return model_pipeline
