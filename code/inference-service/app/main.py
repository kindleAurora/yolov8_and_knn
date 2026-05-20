from fastapi import FastAPI

from app.core.config import settings
from app.modules.system.router import api_router, public_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(public_router)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["meta"])
def root() -> dict[str, object]:
    return {
        "service": "cow-monitor-inference",
        "version": settings.app_version,
        "phase": "stage-3",
        "health": "/health",
        "predict": f"{settings.api_prefix}/predict",
    }
