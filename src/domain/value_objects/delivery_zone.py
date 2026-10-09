from enum import StrEnum


class DeliveryZone(StrEnum):
    CENTER = "centre"
    INNER_SUBURBS = "proche_banlieue"
    SUBURBS = "banlieue"
    RURAL = "rurale"
