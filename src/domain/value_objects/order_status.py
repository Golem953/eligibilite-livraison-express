from enum import StrEnum


class OrderStatus(StrEnum):
    """Cycle de vie d'une commande (ADR-0001) : reçue → prédite → labellisée."""

    RECEIVED = "recue"
    PREDICTED = "predite"
    LABELLED = "labellisee"
