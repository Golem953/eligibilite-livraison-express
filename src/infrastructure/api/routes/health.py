from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from config.settings import APP_VERSION, PROJECT_NAME
from infrastructure.api.dependencies import get_model_provider, get_repository
from infrastructure.api.schemas import HealthStatus, ReadinessStatus

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthStatus,
    operation_id="getHealth",
    summary="Sonde de vivacité",
)
def get_health():
    # Ne dépend d'aucune brique externe : répond tant que le processus vit.
    return HealthStatus(service=PROJECT_NAME, version=APP_VERSION)


@router.get(
    "/health/ready",
    response_model=ReadinessStatus,
    operation_id="getReadiness",
    summary="Sonde de disponibilité",
    responses={503: {"model": ReadinessStatus}},
)
def get_readiness(
    repository=Depends(get_repository),
    model_provider=Depends(get_model_provider),
):
    loaded_model = model_provider.get()
    checks = {"model": "loaded" if loaded_model else "not_loaded"}
    try:
        repository.ping()
        checks["order_store"] = "reachable"
    except Exception:
        checks["order_store"] = "unreachable"

    ready = loaded_model is not None and checks["order_store"] == "reachable"
    status = ReadinessStatus(
        status="ready" if ready else "not_ready",
        checks=checks,
        version=loaded_model.version if loaded_model else None,
    )
    return JSONResponse(status_code=200 if ready else 503, content=status.model_dump())
