import logging
from collections.abc import Sequence

from sklearn.model_selection import train_test_split

from ...config import Settings
from ...domain.entities import OrderEntity
from .order_feature import orders_to_dataframe

logger = logging.getLogger(__name__)

class TrainTestSplitter:
    def __init__(self, random_seed: int | None = None):
        if random_seed is None:
            random_seed = Settings().random_seed
        self.random_seed = random_seed

    def split(
        self,
        orders: Sequence[OrderEntity],
        labels: Sequence[int],
    ):
        if len(orders) != len(labels):
            raise ValueError("Le nombre de commandes doit correspondre au nombre de labels")

        logger.info("Préparation des features (commandes=%d)", len(orders))
        features = orders_to_dataframe(orders)
        split = train_test_split(
            features,
            list(labels),
            test_size=0.20,
            random_state=self.random_seed,
            stratify=list(labels),
        )
        X_train, X_test, _, _ = split
        logger.info(
            "Split terminé (train=%d, test=%d, features=%d)",
            len(X_train),
            len(X_test),
            X_train.shape[1],
        )
        return split

    split_data = split
