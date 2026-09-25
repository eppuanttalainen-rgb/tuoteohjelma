from app.routers.documents import router as documents_router
from app.routers.machines import router as machines_router
from app.routers.projects import router as projects_router

__all__ = ["documents_router", "machines_router", "projects_router"]
