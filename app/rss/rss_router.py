from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from shared_backend.security.internal_service_auth import require_internal_service_token
from app.rss.services.rss_icon_service import get_rss_icon_file_path


rss_public_router = APIRouter(
    prefix="/internal/content/rss",
    tags=["rss"],
    dependencies=[Depends(require_internal_service_token)],
)


@rss_public_router.get("/img/{icon_url:path}", response_class=FileResponse)
def read_rss_icon(icon_url: str) -> FileResponse:
    icon_path = get_rss_icon_file_path(icon_url)
    return FileResponse(
        path=icon_path,
        media_type="image/svg+xml",
        filename=icon_path.name,
    )
