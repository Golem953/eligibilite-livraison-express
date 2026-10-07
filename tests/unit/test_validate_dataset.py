"""Contrôles qualité (repris du notebook, section « Simulation de données
incorrectes »)."""

import pandas as pd
import pytest
from generate_orders import GenerateOrders

from infrastructure.config.training_config import get_training_config
from infrastructure.ml.transform.validate_dataset import ValidateDataset


def test_validate_refuse_une_ligne_dupliquee():
    orders = GenerateOrders(n_rows=100).generate()

    orders_test = orders.copy()

    # Ajout volontaire d'une ligne dupliquée
    orders_test = pd.concat([orders_test, orders_test.iloc[[0]]], ignore_index=True)

    config = get_training_config()
    with pytest.raises(
        ValueError, match="Des identifiants de commande sont dupliqués."
    ):
        ValidateDataset(
            orders_test, config.quality, config.features.target_column
        ).validate()
