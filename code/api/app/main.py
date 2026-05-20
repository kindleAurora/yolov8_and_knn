from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.alerts.router import router as alerts_router
from app.modules.auth.router import router as auth_router
from app.modules.devices.router import router as devices_router
from app.modules.events.router import router as events_router
from app.modules.history.router import router as history_router
from app.modules.media.router import router as media_router
from app.modules.rules.router import router as rules_router
from app.modules.system.router import api_router, public_router
from app.modules.zones.router import router as zones_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(devices_router, prefix=settings.api_prefix)
app.include_router(zones_router, prefix=settings.api_prefix)
app.include_router(events_router, prefix=settings.api_prefix)
app.include_router(alerts_router, prefix=settings.api_prefix)
app.include_router(rules_router, prefix=settings.api_prefix)
app.include_router(history_router, prefix=settings.api_prefix)
app.include_router(media_router, prefix=settings.api_prefix)


@app.get("/", tags=["meta"])
def root() -> dict[str, object]:
    return {
        "service": "cow-monitor-api",
        "version": settings.app_version,
        "phase": "stage-4",
        "docs": "/docs",
        "health": "/health",
    }
