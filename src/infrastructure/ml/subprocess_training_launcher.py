import subprocess
import sys
import threading

from infrastructure.interface.training_launcher_interface import (
    TrainingLauncherInterface,
)

TRAIN_COMMAND = [sys.executable, "-m", "infrastructure.adapter.cli.train"]


class SubprocessTrainingLauncher(TrainingLauncherInterface):
    """Lance la CLI d'entraînement dans un processus séparé : un entraînement
    long ou qui plante ne bloque pas l'API. Sa sortie va dans les logs de l'API.
    Un seul entraînement à la fois."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    def start(self) -> int:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError(
                    "Un entraînement est déjà en cours "
                    f"(processus {self._process.pid})."
                )
            self._process = subprocess.Popen(TRAIN_COMMAND)
            return self._process.pid
