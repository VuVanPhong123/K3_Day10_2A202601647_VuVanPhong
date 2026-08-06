from __future__ import annotations

from datetime import UTC, datetime
import html
import json
from pathlib import Path
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from .crossref import PaperRecord


CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "text_for_embedding",
    "abs_url",
    "pdf_url",
]


def _empty_clean_frame() -> pd.DataFrame:
    """Return an empty frame with the stable downstream schema and dtypes."""
    frame = pd.DataFrame({column: pd.Series(dtype="object") for column in CLEAN_COLUMNS})
    frame["age_days"] = pd.Series(dtype="int64")
    frame["summary_chars"] = pd.Series(dtype="int64")
    return frame


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_whitespace(text)


def _normalise_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = _clean_text(item)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            items.append(cleaned)
    return items


def _parse_timestamp(value: object) -> pd.Timestamp | None:
    if value is None or not str(value).strip():
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def _iso_date(value: object) -> str:
    parsed = _parse_timestamp(value)
    return parsed.date().isoformat() if parsed is not None else ""


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw Crossref records into the deterministic clean contract.

    Invalid publication dates remain visible as ``published=""`` and
    ``age_days=-1`` so observability can report the defect instead of treating
    it as a fresh record.  The input dataclasses and their lists are never
    mutated.
    """
    if not records:
        return _empty_clean_frame()

    reference = pd.Timestamp(run_date)
    if reference.tzinfo is None:
        reference = reference.tz_localize(UTC)
    else:
        reference = reference.tz_convert(UTC)

    rows: list[dict[str, object]] = []
    for record in records:
        paper_id = _clean_text(record.paper_id)
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        authors = _normalise_items(record.authors)
        categories = _normalise_items(record.categories)
        published_ts = _parse_timestamp(record.published)

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors_joined": compact_join(authors),
                "categories_joined": compact_join(categories),
                "published": published_ts.date().isoformat() if published_ts is not None else "",
                "updated": _iso_date(record.updated),
                "age_days": (reference - published_ts).days if published_ts is not None else -1,
                "summary_chars": len(summary),
                "text_for_embedding": normalize_whitespace(
                    f"Title: {title} Summary: {summary} Authors: {compact_join(authors)} "
                    f"Categories: {compact_join(categories)}"
                ),
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
            }
        )

    frame = pd.DataFrame(rows, columns=CLEAN_COLUMNS)
    frame["title_key"] = frame["title"].str.casefold()

    # Sort before de-duplication so output and survivor selection are stable
    # regardless of the order in which the source API returned records.
    frame = frame.sort_values(
        by=["paper_id", "title_key", "summary", "published"],
        ascending=[True, True, True, True],
        kind="mergesort",
    )
    frame = frame[
        (frame["paper_id"] != "")
        & (frame["title"] != "")
        & (frame["summary"] != "")
    ].copy()
    if frame.empty:
        return _empty_clean_frame()

    frame = frame.drop_duplicates(subset=["paper_id"], keep="first")
    frame = frame.drop_duplicates(subset=["title_key"], keep="first")
    frame = frame.sort_values(
        by=["published", "paper_id"],
        ascending=[False, True],
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)
    frame = frame[CLEAN_COLUMNS]
    frame["age_days"] = frame["age_days"].astype("int64")
    frame["summary_chars"] = frame["summary_chars"].astype("int64")
    return frame


def save_clean_data(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    """Persist the clean contract as UTF-8 CSV and JSON artifacts."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    output = df.reindex(columns=CLEAN_COLUMNS).copy()
    output.to_csv(csv_path, index=False, encoding="utf-8")
    json_path.write_text(
        json.dumps(output.to_dict(orient="records"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
