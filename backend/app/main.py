from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.commercial.api.routes_customers import router as customers_router
from app.commercial.api.routes_followups import (
    global_router as followups_global_router,
    router as followups_router,
)
from app.commercial.api.routes_interactions import router as interactions_router
from app.foundation.api.routes_auth import router as auth_router


configure_logging()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
)

register_middleware(app)
app.include_router(auth_router, prefix=f"{settings.api_prefix}/auth")
app.include_router(customers_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(interactions_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(followups_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(followups_global_router, prefix=f"{settings.api_prefix}/commercial")


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
    }
