from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import (
    documents_router,
    facts_router,
    machines_router,
    projects_router,
    reconciliation_router,
    snapshots_router,
    verification_router,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Evidence-first API for reconstructing the current state of existing industrial machinery."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(machines_router)
app.include_router(documents_router)
app.include_router(facts_router)
app.include_router(reconciliation_router)
app.include_router(verification_router)
app.include_router(snapshots_router)


@app.get("/api/v1/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api", "version": "0.1.0"}
