from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.auth import router as auth_router
from app.routes.processes import router as processes_router

app = FastAPI(
    title="Portically Processos API",
    version=settings.app_version,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_router)
app.include_router(processes_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "portically-processos-api",
        "version": settings.app_version,
    }
