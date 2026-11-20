import logging
from collections.abc import Sequence

from ...domain.entities.order_entity import OrderEntity
from .order_feature import orders_to_dataframe
from .train_test_splitter import TrainTestSplitter

logger = logging.getLogger(__name__)


class ChronologicalTrainTestSplitter(TrainTestSplitter):
    """Découpage dans l'ordre d'arrivée : les 20 % de commandes les plus récentes forment le test.

    Utilisé pour les commandes de l'ERP, que le repository renvoie dans leur ordre
    d'arrivée. Quand les données grandissent, le jeu de test est toujours fait de
    commandes plus récentes que celles qui ont entraîné le modèle en service : les deux
    modèles sont comparés sur des commandes qu'aucun n'a vues (ADR-0009).
    """

    def split(
        self,
        orders: Sequence[OrderEntity],
        labels: Sequence[int],
    ):
        if len(orders) != len(labels):
            raise ValueError("Le nombre de commandes doit correspondre au nombre de labels")

        logger.info("Préparation des features (commandes=%d)", len(orders))
        features = orders_to_dataframe(orders)
        cut = int(len(orders) * 0.80)
        X_train, X_test = features.iloc[:cut], features.iloc[cut:]
        y_train, y_test = list(labels[:cut]), list(labels[cut:])
        logger.info(
            "Split chronologique terminé (train=%d, test=%d, features=%d)",
            len(X_train),
            len(X_test),
            X_train.shape[1],
        )
        return X_train, X_test, y_train, y_test
