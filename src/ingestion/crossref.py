from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from typing import Any

import requests

from core.config import Settings


CROSSREF_API_URL = "https://api.crossref.org/works"
REQUEST_TIMEOUT_SECONDS = 30
MAX_REQUEST_ATTEMPTS = 4
INITIAL_BACKOFF_SECONDS = 1.0
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


class _MarkupTextExtractor(HTMLParser):
    """Extract readable text from the HTML/JATS fragments returned by Crossref."""

    _BLOCK_TAGS = {
        "abstract",
        "br",
        "div",
        "fig",
        "figcaption",
        "li",
        "p",
        "sec",
        "table",
        "td",
        "th",
        "title",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    @staticmethod
    def _local_tag(tag: str) -> str:
        return tag.rsplit(":", maxsplit=1)[-1].lower()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if self._local_tag(tag) in self._BLOCK_TAGS:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._local_tag(tag) in self._BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _clean_markup(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parser = _MarkupTextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        # Crossref occasionally contains malformed fragments. HTMLParser is
        # tolerant, but returning the text parsed so far is safer than losing
        # the complete record if an unusual fragment still raises.
        pass
    return " ".join("".join(parser.parts).split())


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        value = next((item for item in value if isinstance(item, str) and item.strip()), "")
    return _clean_markup(value)


def _date_from_message(value: Any) -> str:
    """Return a stable ISO date from a Crossref date object."""

    if not isinstance(value, dict):
        return ""

    date_time = value.get("date-time")
    if isinstance(date_time, str) and date_time.strip():
        # Crossref date-time values are ISO-8601. The date prefix avoids
        # timezone parsing differences while keeping the ingestion contract.
        return date_time.strip()[:10]

    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts or not isinstance(date_parts[0], list):
        return ""

    parts = date_parts[0]
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (IndexError, TypeError, ValueError):
        return ""


def _first_date(item: dict[str, Any], *field_names: str) -> str:
    for field_name in field_names:
        parsed = _date_from_message(item.get(field_name))
        if parsed:
            return parsed
    return ""


def _parse_authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    authors: list[str] = []
    for author in value:
        if not isinstance(author, dict):
            continue
        given = _clean_markup(author.get("given"))
        family = _clean_markup(author.get("family"))
        name = " ".join(part for part in (given, family) if part)
        if not name:
            name = _clean_markup(author.get("name"))
        if name:
            authors.append(name)
    return authors


def _parse_categories(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [category for item in value if (category := _clean_markup(item))]


def _pdf_url(item: dict[str, Any]) -> str:
    links = item.get("link")
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            url = link.get("URL")
            content_type = str(link.get("content-type", "")).lower()
            if isinstance(url, str) and url.strip() and (
                "pdf" in content_type or url.lower().split("?", maxsplit=1)[0].endswith(".pdf")
            ):
                return url.strip()
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref works response into valid :class:`PaperRecord` objects.

    Records without a DOI, title, or abstract are deliberately excluded. Raw
    metadata is otherwise preserved as closely as the PaperRecord schema allows.
    """

    if not isinstance(payload, dict):
        return []
    message = payload.get("message")
    if not isinstance(message, dict):
        return []
    items = message.get("items")
    if not isinstance(items, list):
        return []

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        doi = _clean_markup(item.get("DOI"))
        title = _first_text(item.get("title"))
        abstract = _clean_markup(item.get("abstract"))
        if not doi or not title or not abstract:
            continue

        categories = _parse_categories(item.get("subject"))
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=abstract,
                authors=_parse_authors(item.get("author")),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=_first_date(
                    item,
                    "published",
                    "published-online",
                    "published-print",
                    "issued",
                    "created",
                ),
                updated=_first_date(item, "updated", "deposited", "indexed"),
                abs_url=_clean_markup(item.get("URL")),
                pdf_url=_pdf_url(item),
                comment=_first_text(item.get("subtitle")),
            )
        )
    return records


def _retry_delay_seconds(response: requests.Response | None, attempt_index: int) -> float:
    if response is not None:
        retry_after = getattr(response, "headers", {}).get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return INITIAL_BACKOFF_SECONDS * (2**attempt_index)


def _request_crossref(params: dict[str, Any]) -> requests.Response:
    last_error: requests.RequestException | None = None
    for attempt_index in range(MAX_REQUEST_ATTEMPTS):
        response: requests.Response | None = None
        try:
            response = requests.get(
                CROSSREF_API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                return response
            last_error = requests.HTTPError(
                f"Crossref returned retryable HTTP {response.status_code}",
                response=response,
            )

        if attempt_index < MAX_REQUEST_ATTEMPTS - 1:
            time.sleep(_retry_delay_seconds(response, attempt_index))

    assert last_error is not None
    raise last_error


def _write_json_utf8(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref works, persist the raw response, and persist parsed records."""

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    response = _request_crossref(params)
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Crossref response must be a JSON object.")

    _write_json_utf8(settings.paths.raw_api_response, payload)
    records = parse_crossref_payload(payload)
    _write_json_utf8(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the parsed raw-record snapshot written by :func:`fetch_source_records`."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Raw records snapshot must contain a JSON list: {path}")

    records: list[PaperRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} must be a JSON object.")
        try:
            records.append(PaperRecord(**item))
        except TypeError as exc:
            raise ValueError(f"Invalid raw record at index {index}: {exc}") from exc
    return records
