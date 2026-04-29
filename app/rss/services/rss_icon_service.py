from pathlib import Path

from app.errors.custom_exceptions import RssIconNotFoundError
from app.rss.domain.rss_repository_config import get_rss_feeds_repository_path


def get_rss_icon_file_path(icon_url: str) -> Path:
    icon_url = icon_url.strip()
    if not icon_url:
        raise RssIconNotFoundError("Icon path is empty.")

    icon_path = Path(icon_url.lstrip("/"))
    if icon_path.is_absolute() or ".." in icon_path.parts:
        raise RssIconNotFoundError("Icon path is invalid.")

    if icon_path.parts[:1] != ("img",):
        icon_path = Path("img") / icon_path

    repository_path = get_rss_feeds_repository_path().resolve()
    icon_path = (repository_path / icon_path).resolve()

    if not icon_path.is_relative_to(repository_path):
        raise RssIconNotFoundError("Icon path is invalid.")
    if icon_path.suffix.lower() != ".svg":
        raise RssIconNotFoundError("Only svg icons are supported.")
    if not icon_path.is_file():
        raise RssIconNotFoundError(f"Icon not found: {icon_url}")

    return icon_path
