from __future__ import annotations

from fastapi import APIRouter

from .user_source_router import user_sources_router


internal_content_router = APIRouter()
internal_content_router.include_router(user_sources_router)
