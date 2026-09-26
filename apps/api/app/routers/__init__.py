from app.routers.documents import router as documents_router
from app.routers.facts import router as facts_router
from app.routers.machines import router as machines_router
from app.routers.projects import router as projects_router
from app.routers.reconciliation import router as reconciliation_router

__all__ = [
    "documents_router",
    "facts_router",
    "machines_router",
    "projects_router",
    "reconciliation_router",
]
