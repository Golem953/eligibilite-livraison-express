import logging
import threading
import time

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 30


class ModelProvider:
    """Garde en mémoire le modèle servi, chargé une seule fois depuis le registre.

    Tant qu'aucun modèle n'est disponible (pas encore entraîné, MLflow injoignable),
    un nouvel essai est fait au plus toutes les RETRY_DELAY_SECONDS secondes.
    """

    def __init__(self, registry):
        self.registry = registry
        self._loaded = None
        self._last_attempt = None
        self._lock = threading.Lock()

    def get(self):
        if self._loaded is not None:
            return self._loaded

        with self._lock:
            now = time.monotonic()
            retry_allowed = (
                self._last_attempt is None
                or now - self._last_attempt >= RETRY_DELAY_SECONDS
            )
            if self._loaded is None and retry_allowed:
                self._last_attempt = now
                try:
                    self._loaded = self.registry.load_champion()
                    logger.info("Modèle chargé : version %s", self._loaded.version)
                except Exception as error:
                    logger.warning("Modèle indisponible : %s", error)

        return self._loaded
