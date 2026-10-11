from fastapi import APIRouter, Depends

from infrastructure.api.dependencies import get_model_provider
from infrastructure.api.errors import error_responses
from infrastructure.api.prediction import require_model
from infrastructure.api.schemas import ModelCardResponse
from infrastructure.ml.model_card import ModelCard

router = APIRouter(prefix="/v1/model", tags=["model"])


@router.get(
    "",
    response_model=ModelCardResponse,
    operation_id="getModelCard",
    summary="Métadonnées et métriques du modèle en service",
    responses=error_responses(503),
)
def get_model_card(model_provider=Depends(get_model_provider)):
    """Model card de la cellule 55 du notebook, pour la version servie."""
    return ModelCard.build_model_card(require_model(model_provider))
