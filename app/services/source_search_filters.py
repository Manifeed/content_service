from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from shared_backend.schemas.sources.source_schema import AppliedSearchFilterRead


SOURCE_SEARCH_PERIODS: dict[str, timedelta | None] = {
    "all": None,
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "1m": timedelta(days=31),
    "1y": timedelta(days=365),
}


@dataclass(frozen=True)
class ResolvedSourceSearchFilters:
    country: str | None = None
    language: str | None = None
    company_id: int | None = None
    author_id: int | None = None
    published_from: datetime | None = None
    applied_filters: list[AppliedSearchFilterRead] = field(default_factory=list)


def resolve_source_search_filters(
    *,
    explicit_country: str | None,
    explicit_language: str | None,
    explicit_company_id: int | None,
    explicit_author_id: int | None,
    explicit_period: str | None,
) -> ResolvedSourceSearchFilters:
    applied_filters: list[AppliedSearchFilterRead] = []

    country = normalize_source_search_country(explicit_country)
    if country:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="country",
                value=country,
                label=f"Country: {country.upper()}",
            )
        )

    language = normalize_source_search_language(explicit_language)
    if language:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="language",
                value=language,
                label=f"Language: {language.upper()}",
            )
        )

    if explicit_company_id is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="company_id",
                value=explicit_company_id,
                label=f"Company #{explicit_company_id}",
            )
        )

    if explicit_author_id is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="author_id",
                value=explicit_author_id,
                label=f"Author #{explicit_author_id}",
            )
        )

    resolved_period = normalize_source_search_period(explicit_period)
    resolved_published_from = resolve_source_search_period_start(resolved_period)
    if resolved_published_from is not None:
        applied_filters.append(
            AppliedSearchFilterRead(
                field="published_period",
                value=resolved_period,
                label=f"Period: {resolved_period.upper()}",
            )
        )

    return ResolvedSourceSearchFilters(
        country=country,
        language=language,
        company_id=explicit_company_id,
        author_id=explicit_author_id,
        published_from=resolved_published_from,
        applied_filters=applied_filters,
    )


def normalize_source_search_period(value: str | None) -> str:
    normalized = (value or "all").strip().casefold()
    return normalized if normalized in SOURCE_SEARCH_PERIODS else "all"


def resolve_source_search_period_start(period: str) -> datetime | None:
    delta = SOURCE_SEARCH_PERIODS[period]
    if delta is None:
        return None
    return datetime.now(UTC) - delta


def normalize_source_search_country(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()[:2]
    return normalized or None


def normalize_source_search_language(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()[:3]
    return normalized or None
