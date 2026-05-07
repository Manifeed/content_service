from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import calendar
import re
import unicodedata


@dataclass(frozen=True)
class ParsedNaturalFilter:
    value: object
    raw_text: str


@dataclass(frozen=True)
class ParsedSourceSearchQuery:
    raw_query: str
    subject_query: str
    language: ParsedNaturalFilter | None = None
    publisher_name: ParsedNaturalFilter | None = None
    author_name: ParsedNaturalFilter | None = None
    published_from: ParsedNaturalFilter | None = None
    published_to: ParsedNaturalFilter | None = None


_LANGUAGE_ALIASES = {
    "francais": "fr",
    "francaise": "fr",
    "francaises": "fr",
    "anglais": "en",
    "anglaise": "en",
    "anglaises": "en",
    "allemand": "de",
    "allemande": "de",
    "allemands": "de",
    "espagnol": "es",
    "espagnole": "es",
    "espagnols": "es",
    "italien": "it",
    "italienne": "it",
    "italiens": "it",
    "portugais": "pt",
    "portugaise": "pt",
}
_MONTH_ALIASES = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
_BOUNDARY_TERMS = (
    "apres",
    "avant",
    "depuis",
    "entre",
    "cette semaine",
    "ce mois-ci",
    "ce mois ci",
)


def parse_source_search_query(
    query: str | None,
    *,
    now: datetime | None = None,
) -> ParsedSourceSearchQuery:
    raw_query = (query or "").strip()
    if not raw_query:
        return ParsedSourceSearchQuery(raw_query="", subject_query="")

    reference_now = _ensure_utc(now or datetime.now(UTC))
    normalized_query = _normalize_text(raw_query)
    consumed_spans: list[tuple[int, int]] = []

    language = _extract_language_filter(raw_query, normalized_query, consumed_spans)
    publisher_name = _extract_named_filter(
        raw_query,
        normalized_query,
        consumed_spans,
        pattern=r"\bpubl\w*\s+par\s+(.+?)(?=\s+(?:"
        + "|".join(re.escape(term) for term in _BOUNDARY_TERMS)
        + r")\b|$)",
    )
    author_name = _extract_named_filter(
        raw_query,
        normalized_query,
        consumed_spans,
        pattern=r"\becri\w*\s+par\s+(.+?)(?=\s+(?:"
        + "|".join(re.escape(term) for term in _BOUNDARY_TERMS)
        + r")\b|$)",
    )
    range_from, range_to = _extract_between_filter(
        raw_query,
        normalized_query,
        consumed_spans,
    )
    relative_from, relative_to = _extract_relative_date_filter(
        raw_query,
        normalized_query,
        consumed_spans,
        now=reference_now,
    )
    lower_bound = range_from or relative_from or _extract_single_date_filter(
        raw_query,
        normalized_query,
        consumed_spans,
        keyword="depuis",
        is_end=False,
    ) or _extract_single_date_filter(
        raw_query,
        normalized_query,
        consumed_spans,
        keyword="apres",
        is_end=False,
    )
    upper_bound = range_to or relative_to or _extract_single_date_filter(
        raw_query,
        normalized_query,
        consumed_spans,
        keyword="avant",
        is_end=True,
    )

    subject_query = _cleanup_subject_query(_remove_spans(raw_query, consumed_spans))
    return ParsedSourceSearchQuery(
        raw_query=raw_query,
        subject_query=subject_query,
        language=language,
        publisher_name=publisher_name,
        author_name=author_name,
        published_from=lower_bound,
        published_to=upper_bound,
    )


def build_e5_query_input(subject_query: str) -> str:
    return f"query: {_normalize_whitespace(subject_query)}"


def normalize_embedding_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def _extract_language_filter(
    raw_query: str,
    normalized_query: str,
    consumed_spans: list[tuple[int, int]],
) -> ParsedNaturalFilter | None:
    for alias, language in _LANGUAGE_ALIASES.items():
        patterns = [
            rf"\ben\s+{re.escape(alias)}\b",
            rf"\b(?:article|articles|source|sources)?\s*{re.escape(alias)}\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized_query)
            if match is None:
                continue
            consumed_spans.append(match.span())
            return ParsedNaturalFilter(
                value=language,
                raw_text=raw_query[match.start():match.end()].strip(),
            )
    return None


def _extract_named_filter(
    raw_query: str,
    normalized_query: str,
    consumed_spans: list[tuple[int, int]],
    *,
    pattern: str,
) -> ParsedNaturalFilter | None:
    match = re.search(pattern, normalized_query)
    if match is None:
        return None
    raw_name = raw_query[match.start(1):match.end(1)].strip(" .,:;")
    if not raw_name:
        return None
    consumed_spans.append(match.span())
    return ParsedNaturalFilter(
        value=raw_name,
        raw_text=raw_query[match.start():match.end()].strip(),
    )


def _extract_between_filter(
    raw_query: str,
    normalized_query: str,
    consumed_spans: list[tuple[int, int]],
) -> tuple[ParsedNaturalFilter | None, ParsedNaturalFilter | None]:
    match = re.search(r"\bentre\s+(.+?)\s+(?:et|a)\s+(.+?)(?=$)", normalized_query)
    if match is None:
        return None, None

    raw_from = raw_query[match.start(1):match.end(1)].strip(" .,:;")
    raw_to = raw_query[match.start(2):match.end(2)].strip(" .,:;")
    parsed_from = _parse_date_phrase(raw_from, is_end=False)
    parsed_to = _parse_date_phrase(raw_to, is_end=True)
    if parsed_from is None or parsed_to is None:
        return None, None

    consumed_spans.append(match.span())
    return (
        ParsedNaturalFilter(value=parsed_from, raw_text=f"entre {raw_from}"),
        ParsedNaturalFilter(value=parsed_to, raw_text=f"et {raw_to}"),
    )


def _extract_relative_date_filter(
    raw_query: str,
    normalized_query: str,
    consumed_spans: list[tuple[int, int]],
    *,
    now: datetime,
) -> tuple[ParsedNaturalFilter | None, ParsedNaturalFilter | None]:
    week_match = re.search(r"\bcette\s+semaine\b", normalized_query)
    if week_match is not None:
        start = _start_of_week(now)
        consumed_spans.append(week_match.span())
        return (
            ParsedNaturalFilter(value=start, raw_text=raw_query[week_match.start():week_match.end()].strip()),
            ParsedNaturalFilter(value=now, raw_text=raw_query[week_match.start():week_match.end()].strip()),
        )

    month_match = re.search(r"\bce\s+mois(?:-ci|\s+ci)?\b", normalized_query)
    if month_match is not None:
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        consumed_spans.append(month_match.span())
        return (
            ParsedNaturalFilter(value=start, raw_text=raw_query[month_match.start():month_match.end()].strip()),
            ParsedNaturalFilter(value=now, raw_text=raw_query[month_match.start():month_match.end()].strip()),
        )
    return None, None


def _extract_single_date_filter(
    raw_query: str,
    normalized_query: str,
    consumed_spans: list[tuple[int, int]],
    *,
    keyword: str,
    is_end: bool,
) -> ParsedNaturalFilter | None:
    match = re.search(rf"\b{keyword}\s+(.+?)(?=$)", normalized_query)
    if match is None:
        return None
    raw_date = raw_query[match.start(1):match.end(1)].strip(" .,:;")
    parsed = _parse_date_phrase(raw_date, is_end=is_end)
    if parsed is None:
        return None
    consumed_spans.append(match.span())
    return ParsedNaturalFilter(
        value=parsed,
        raw_text=raw_query[match.start():match.end()].strip(),
    )


def _parse_date_phrase(value: str, *, is_end: bool) -> datetime | None:
    normalized = _normalize_text(value).strip()
    if not normalized:
        return None

    iso_match = re.fullmatch(r"(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?", normalized)
    if iso_match is not None:
        year = int(iso_match.group(1))
        month = int(iso_match.group(2))
        day = int(iso_match.group(3) or (calendar.monthrange(year, month)[1] if is_end else 1))
        return _build_datetime(year, month, day, is_end=is_end)

    day_month_match = re.fullmatch(
        r"(\d{1,2})\s+([a-z]+)\s+(\d{4})",
        normalized,
    )
    if day_month_match is not None:
        month = _MONTH_ALIASES.get(day_month_match.group(2))
        if month is None:
            return None
        return _build_datetime(
            int(day_month_match.group(3)),
            month,
            int(day_month_match.group(1)),
            is_end=is_end,
        )

    month_match = re.fullmatch(r"([a-z]+)\s+(\d{4})", normalized)
    if month_match is not None:
        month = _MONTH_ALIASES.get(month_match.group(1))
        if month is None:
            return None
        year = int(month_match.group(2))
        day = calendar.monthrange(year, month)[1] if is_end else 1
        return _build_datetime(year, month, day, is_end=is_end)

    year_match = re.fullmatch(r"(\d{4})", normalized)
    if year_match is not None:
        year = int(year_match.group(1))
        month = 12 if is_end else 1
        day = 31 if is_end else 1
        return _build_datetime(year, month, day, is_end=is_end)
    return None


def _build_datetime(year: int, month: int, day: int, *, is_end: bool) -> datetime | None:
    try:
        if is_end:
            return datetime(year, month, day, 23, 59, 59, 999000, tzinfo=UTC)
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _start_of_week(value: datetime) -> datetime:
    start = value - timedelta(days=value.weekday())
    return datetime(start.year, start.month, start.day, tzinfo=UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _remove_spans(value: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return value
    characters = list(value)
    for start, end in spans:
        for index in range(max(0, start), min(len(characters), end)):
            characters[index] = " "
    return "".join(characters)


def _cleanup_subject_query(value: str) -> str:
    cleaned = _normalize_whitespace(value.strip(" .,:;"))
    cleaned = re.sub(r"^(?:article|articles|source|sources)\s+", "", cleaned, flags=re.IGNORECASE)
    if _normalize_text(cleaned) in {"article", "articles", "source", "sources"}:
        return ""
    return cleaned


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(character for character in decomposed if not unicodedata.combining(character))
    return without_accents.lower()
