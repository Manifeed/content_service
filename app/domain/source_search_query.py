from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class ParsedSourceSearchQuery:
    raw_query: str
    subject_query: str


def parse_source_search_query(query: str | None) -> ParsedSourceSearchQuery:
    raw_query = (query or "").strip()
    return ParsedSourceSearchQuery(
        raw_query=raw_query,
        subject_query=normalize_search_query(raw_query),
    )


def normalize_search_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return _normalize_whitespace(normalized.strip(" .,:;"))


def normalize_precision_query(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", normalize_search_query(value))
    without_accents = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    return _normalize_whitespace(without_accents)


def is_precision_first_query(value: str) -> bool:
    terms = normalize_precision_query(value).split()
    return 0 < len(terms) <= 3 and all(len(term) <= 32 for term in terms)


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
