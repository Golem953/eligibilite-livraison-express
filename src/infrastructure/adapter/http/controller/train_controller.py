from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from infrastructure.adapter.dependency_injection.container import (
    get_training_launcher,
)
from infrastructure.interface.training_launcher_interface import (
    TrainingLauncherInterface,
)

router = APIRouter()


@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
def train(
    launcher: Annotated[TrainingLauncherInterface, Depends(get_training_launcher)],
) -> dict[str, str | int]:
    """Lance l'entraînement en arrière-plan et répond immédiatement.

    Le résultat (version, métriques) est visible dans les logs de l'API et
    dans MLflow.
    """
    try:
        pid = launcher.start()
    except RuntimeError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return {"status": "started", "pid": pid}
