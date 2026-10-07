from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

ORDER_ID_MAX_LENGTH = 50
MODEL_VERSION_MAX_LENGTH = 50
WEATHER_VALUES = frozenset({"normal", "pluie", "neige", "orage"})
DELIVERY_ZONES = frozenset({"centre", "proche_banlieue", "banlieue", "rurale"})
CUSTOMER_TYPES = frozenset({"standard", "premium"})


class OrderStatus(StrEnum):
    """Cycle de vie d'une commande (ADR-0001) : reçue → prédite → labellisée."""

    RECEIVED = "recue"
    PREDICTED = "predite"
    LABELLED = "labellisee"


@dataclass(frozen=True)
class Prediction:
    """Résultat du modèle pour une commande.

    Ce n'est pas un label : la vérité terrain est le label réel, remonté plus tard
    (ADR-0001).
    """

    eligible: bool
    probability: float
    model_version: str
    predicted_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.eligible, bool):
            raise ValueError("eligible doit être un booléen.")
        if isinstance(self.probability, bool) or not isinstance(
            self.probability, int | float
        ):
            raise ValueError("probability doit être un nombre.")
        if not 0 <= self.probability <= 1:
            raise ValueError("probability doit être comprise entre 0 et 1.")
        if not isinstance(self.model_version, str) or not (
            1 <= len(self.model_version) <= MODEL_VERSION_MAX_LENGTH
        ):
            raise ValueError(
                f"model_version doit contenir entre 1 et {MODEL_VERSION_MAX_LENGTH} "
                "caractères."
            )
        if (
            not isinstance(self.predicted_at, datetime)
            or self.predicted_at.tzinfo is None
        ):
            raise ValueError("predicted_at doit être une date avec fuseau horaire.")


@dataclass(frozen=True)
class Order:
    """Commande reçue par l'API, avec ses variables, sa prédiction et son label réel.

    Les règles de validité reprennent les contrôles qualité du notebook
    d'exploration. Une commande invalide ne peut pas être construite.
    """

    order_id: str
    order_date: datetime
    hour: int
    day_of_week: int
    weekend: bool
    distance_km: float
    order_value_eur: float
    weight_kg: float
    stock_available: bool
    preparation_time_min: float
    carrier_capacity: float
    weather: str
    delivery_zone: str
    customer_type: str
    status: OrderStatus = OrderStatus.RECEIVED
    prediction: Prediction | None = None
    real_label: bool | None = None

    def __post_init__(self) -> None:
        self._validate_identity()
        self._validate_features()
        self._validate_status()

    def _validate_identity(self) -> None:
        if not isinstance(self.order_id, str) or not (
            1 <= len(self.order_id) <= ORDER_ID_MAX_LENGTH
        ):
            raise ValueError(
                f"order_id doit contenir entre 1 et {ORDER_ID_MAX_LENGTH} caractères."
            )
        if not _is_aware_datetime(self.order_date):
            raise ValueError("order_date doit être une date avec fuseau horaire.")

    def _validate_features(self) -> None:
        _require_int("hour", self.hour, 0, 23)
        _require_int("day_of_week", self.day_of_week, 0, 6)
        _require_bool("weekend", self.weekend)
        if self.weekend != (self.day_of_week >= 5):
            raise ValueError(
                "weekend doit valoir vrai uniquement le samedi et le dimanche "
                "(day_of_week 5 ou 6)."
            )
        _require_number("distance_km", self.distance_km, minimum=0)
        _require_number("order_value_eur", self.order_value_eur, minimum=0)
        _require_number("weight_kg", self.weight_kg, minimum=0)
        _require_bool("stock_available", self.stock_available)
        _require_number("preparation_time_min", self.preparation_time_min, minimum=0)
        _require_number("carrier_capacity", self.carrier_capacity, minimum=0, maximum=1)
        _require_choice("weather", self.weather, WEATHER_VALUES)
        _require_choice("delivery_zone", self.delivery_zone, DELIVERY_ZONES)
        _require_choice("customer_type", self.customer_type, CUSTOMER_TYPES)

    def _validate_status(self) -> None:
        if not isinstance(self.status, OrderStatus):
            raise ValueError("status doit être un OrderStatus.")
        if self.prediction is not None and not isinstance(self.prediction, Prediction):
            raise ValueError("prediction doit être une Prediction.")
        if self.real_label is not None:
            _require_bool("real_label", self.real_label)

        has_prediction = self.prediction is not None
        has_label = self.real_label is not None
        # Une commande labellisée peut ne pas avoir de prédiction : commande
        # historique, antérieure au modèle (données d'amorçage).
        allowed = {
            OrderStatus.RECEIVED: {(False, False)},
            OrderStatus.PREDICTED: {(True, False)},
            OrderStatus.LABELLED: {(True, True), (False, True)},
        }[self.status]
        if (has_prediction, has_label) not in allowed:
            raise ValueError(
                f"Statut « {self.status} » incohérent : prédiction "
                f"{'présente' if has_prediction else 'absente'}, label réel "
                f"{'présent' if has_label else 'absent'}."
            )


def _require_int(name: str, value: object, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} doit être un entier.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} doit être compris entre {minimum} et {maximum}.")


def _require_number(
    name: str, value: object, minimum: float, maximum: float | None = None
) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} doit être un nombre.")
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"≥ {minimum}" if maximum is None else f"entre {minimum} et {maximum}"
        raise ValueError(f"{name} doit être {bounds}.")


def _require_bool(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{name} doit être un booléen.")


def _require_choice(name: str, value: object, allowed: frozenset[str]) -> None:
    if value not in allowed:
        raise ValueError(f"{name} doit valoir l'une de : {sorted(allowed)}.")


def _is_aware_datetime(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None
