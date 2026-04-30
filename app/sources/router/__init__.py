from fastapi import APIRouter, Depends

from shared_backend.security.internal_service_auth import require_internal_service_token
from .source_read_router import source_read_router
from .user_source_read_router import user_source_read_router


admin_sources_router = APIRouter(
    prefix="/internal/content/admin/sources",
    tags=["sources"],
    dependencies=[Depends(require_internal_service_token)],
)
admin_sources_router.include_router(source_read_router)

user_sources_router = APIRouter(
    prefix="/internal/content/sources",
    tags=["sources"],
    dependencies=[Depends(require_internal_service_token)],
)
user_sources_router.include_router(user_source_read_router)

__all__ = ["admin_sources_router", "user_sources_router"]
