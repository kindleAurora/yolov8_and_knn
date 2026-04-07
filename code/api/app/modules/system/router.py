from fastapi import APIRouter

from app.common.responses import success_response
from app.core.config import settings
from app.core.database import check_database, check_inference_service, check_redis

public_router = APIRouter(tags=["健康检查"])
api_router = APIRouter(prefix="/system", tags=["系统信息"])


def _health_payload() -> dict[str, object]:
    database_status, database_detail = check_database()
    redis_status, redis_detail = check_redis()
    inference_status, inference_detail = check_inference_service()

    return {
        "service": "cow-monitor-api",
        "environment": settings.app_env,
        "version": settings.app_version,
        "phase": "stage-3",
        "dependencies": [
            {
                "name": "postgres",
                "status": database_status,
                "detail": database_detail,
            },
            {
                "name": "redis",
                "status": redis_status,
                "detail": redis_detail,
            },
            {
                "name": "inference-service",
                "status": inference_status,
                "detail": inference_detail,
            },
        ],
    }


@public_router.get("/health")
def health() -> dict[str, object]:
    return success_response(_health_payload())


@api_router.get("/health")
def api_health() -> dict[str, object]:
    return success_response(_health_payload())


@api_router.get("/meta")
def meta() -> dict[str, object]:
    return success_response(
        {
            "service": "cow-monitor-api",
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "version": settings.app_version,
            "phase": "stage-3",
            "api_prefix": settings.api_prefix,
        }
    )
