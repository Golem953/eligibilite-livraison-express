from .order_feature import NUMERIC_FEATURES, CATEGORICAL_FEATURES
from ...config import Settings

from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer

class MLPipeline:
    def __init__(self, random_seed: int | None = None):
        if random_seed is None:
            random_seed = Settings().random_seed
        self.random_seed = random_seed

    def get_model_pipeline(self):
        numeric_transformer = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(strategy="median")
                ),
                (
                    "scaler",
                    StandardScaler()
                ),
            ]
        )

        categorical_transformer = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(strategy="most_frequent")
                ),
                (
                    "onehot",
                    OneHotEncoder(
                        handle_unknown="ignore",
                        sparse_output=False
                    )
                ),
            ]
        )

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "numeric",
                    numeric_transformer,
                    NUMERIC_FEATURES
                ),
                (
                    "categorical",
                    categorical_transformer,
                    CATEGORICAL_FEATURES
                ),
            ]
        )

        classifier = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=self.random_seed
        )

        return Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", classifier),
            ]
        )
