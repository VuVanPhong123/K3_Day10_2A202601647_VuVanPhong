from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

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
    """Empty frame that still honours the agreed column names and dtypes."""
    df = pd.DataFrame(columns=CLEAN_COLUMNS)
    for column in ("age_days", "summary_chars"):
        df[column] = df[column].astype("int64")
    return df


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a DataFrame ready for embedding.

    Pipeline:
    1. Convert to DataFrame.
    2. Normalize whitespace in title, summary, authors and categories.
    3. Join authors and categories.
    4. Parse dates to ISO date strings and calculate age_days.
    5. Create text_for_embedding and summary_chars.
    6. Filter invalid rows (missing/empty title, summary, paper_id).
    7. Remove duplicates (by paper_id and by title, keep first).
    8. Sort deterministically by published desc, then paper_id asc.
    """
    if not records:
        return _empty_clean_frame()

    df = pd.DataFrame(
        [
            {
                "paper_id": r.paper_id,
                "title": r.title,
                "summary": r.summary,
                "authors": r.authors,
                "categories": r.categories,
                "published": r.published,
                "updated": r.updated,
                "abs_url": r.abs_url,
                "pdf_url": r.pdf_url,
            }
            for r in records
        ]
    )

    def normalize_items(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned = [normalize_whitespace(str(item)) for item in values if item]
        seen: set[str] = set()
        unique: list[str] = []
        for item in cleaned:
            key = item.lower()
            if item and key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    for column in ("paper_id", "abs_url", "pdf_url"):
        df[column] = df[column].fillna("").astype(str).str.strip()

    df["title"] = df["title"].fillna("").astype(str).apply(normalize_whitespace)
    df["summary"] = df["summary"].fillna("").astype(str).apply(normalize_whitespace)
    df["authors_joined"] = df["authors"].apply(lambda x: compact_join(normalize_items(x)))
    df["categories_joined"] = df["categories"].apply(lambda x: compact_join(normalize_items(x)))
    df["title_key"] = df["title"].str.lower()

    def parse_date(value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def to_iso_date(value: object) -> str:
        parsed = parse_date(value)
        return parsed.date().isoformat() if parsed else ""

    def calc_age_days(value: object) -> int:
        parsed = parse_date(value)
        if parsed is None:
            return -1
        reference = run_date if run_date.tzinfo else run_date.replace(tzinfo=UTC)
        return (reference - parsed).days

    df["age_days"] = df["published"].apply(calc_age_days)
    df["published"] = df["published"].apply(to_iso_date)
    df["updated"] = df["updated"].apply(to_iso_date)
    df["summary_chars"] = df["summary"].apply(len)

    df["text_for_embedding"] = df.apply(
        lambda row: f"{row['title']} {row['summary']} {row['authors_joined']} {row['categories_joined']}",
        axis=1,
    )
    df["text_for_embedding"] = df["text_for_embedding"].apply(normalize_whitespace)

    df = df[
        (df["paper_id"] != "")
        & (df["title"] != "")
        & (df["summary"] != "")
        & (df["text_for_embedding"] != "")
    ].copy()

    if df.empty:
        return _empty_clean_frame()

    # Dedupe on the original record order so the first occurrence wins, then sort.
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    # qa.py resolves an exact document by title, so duplicate titles would make
    # retrieval ambiguous even when paper_id differs.
    df = df.drop_duplicates(subset=["title_key"], keep="first")

    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    df = df[CLEAN_COLUMNS]
    df["age_days"] = df["age_days"].astype("int64")
    df["summary_chars"] = df["summary_chars"].astype("int64")

    return df
