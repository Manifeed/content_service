from __future__ import annotations

from fastapi import APIRouter

from app.routers.admin_source_router import admin_sources_router
from app.routers.analysis_router import analysis_router
from app.routers.user_source_router import user_sources_router


internal_content_router = APIRouter()
internal_content_router.include_router(admin_sources_router)
internal_content_router.include_router(user_sources_router)
internal_content_router.include_router(analysis_router)
