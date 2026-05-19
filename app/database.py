from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from shared_backend.database import (
    check_database_ready,
    configure_database_access,
    get_db_session as shared_get_db_session,
)

_CONTENT_DATABASE = configure_database_access(
    write_env="CONTENT_READ_DATABASE_URL",
    write_fallback_env_names=("CONTENT_DATABASE_URL", "DATABASE_URL"),
)

CONTENT_READ_DATABASE_URL = _CONTENT_DATABASE.read_url

content_read_engine = _CONTENT_DATABASE.read_engine
ContentReadSessionLocal = _CONTENT_DATABASE.read_session_factory


def get_content_read_db_session() -> Generator[Session, None, None]:
    yield from shared_get_db_session(ContentReadSessionLocal)


def check_content_database_ready() -> None:
    check_database_ready(content_read_engine)
