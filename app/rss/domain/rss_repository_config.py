import os
from pathlib import Path

DEFAULT_RSS_FEEDS_REPOSITORY_URL = "https://github.com/Manifeed/rss_feed"
DEFAULT_RSS_FEEDS_REPOSITORY_BRANCH = "main"
DEFAULT_RSS_FEEDS_REPOSITORY_PATH = Path("var/rss_feeds")


def get_rss_feeds_repository_url() -> str:
    return os.getenv("RSS_FEEDS_REPOSITORY_URL", DEFAULT_RSS_FEEDS_REPOSITORY_URL)


def get_rss_feeds_repository_branch() -> str:
    return os.getenv("RSS_FEEDS_REPOSITORY_BRANCH", DEFAULT_RSS_FEEDS_REPOSITORY_BRANCH)


def get_rss_feeds_repository_path() -> Path:
    configured_path = os.getenv("RSS_FEEDS_REPOSITORY_PATH")
    if configured_path:
        return Path(configured_path).expanduser()
    return DEFAULT_RSS_FEEDS_REPOSITORY_PATH
