from __future__ import annotations

from datetime import date, datetime
import html
import json
from pathlib import Path
import re

import pandas as pd

from .crossref import PaperRecord


def _clean_text(text: str | None) -> str:
    """Strip XML/HTML tags and normalize whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _parse_date(date_str: str | None) -> date | None:
    """Parse YYYY-MM-DD string into a datetime.date object."""
    if not date_str or not isinstance(date_str, str):
        return None
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", date_str.strip())
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a structured DataFrame ready for embedding.

    Filtering rules:
    - Drop records missing title or empty title.
    - Drop records missing summary or summary length < 100 characters.
    """
    run_date_val = run_date.date() if isinstance(run_date, datetime) else run_date

    cleaned_rows: list[dict] = []
    for rec in records:
        title = _clean_text(rec.title)
        if not title:
            continue

        summary = _clean_text(rec.summary)
        if not summary or len(summary) < 100:
            continue

        authors_list = rec.authors if isinstance(rec.authors, list) else []
        authors_clean = [a.strip() for a in authors_list if isinstance(a, str) and a.strip()]
        authors_joined = ", ".join(authors_clean) if authors_clean else "Unknown"

        categories_list = rec.categories if isinstance(rec.categories, list) else []
        categories_clean = [c.strip() for c in categories_list if isinstance(c, str) and c.strip()]
        categories_joined = ", ".join(categories_clean) if categories_clean else "Uncategorized"

        primary_category = (
            rec.primary_category
            if rec.primary_category and rec.primary_category != "Uncategorized"
            else (categories_clean[0] if categories_clean else "Uncategorized")
        )

        pub_d = _parse_date(rec.published)
        if pub_d:
            published_str = pub_d.isoformat()
            age_days = max(0, (run_date_val - pub_d).days)
        else:
            published_str = rec.published if rec.published else "1970-01-01"
            age_days = 0

        upd_d = _parse_date(rec.updated)
        updated_str = upd_d.isoformat() if upd_d else (rec.updated if rec.updated else published_str)

        summary_chars = len(summary)
        text_for_embedding = f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"

        cleaned_rows.append(
            {
                "paper_id": str(rec.paper_id).strip(),
                "title": title,
                "summary": summary,
                "authors": authors_clean,
                "categories": categories_clean,
                "primary_category": primary_category,
                "published": published_str,
                "updated": updated_str,
                "abs_url": str(rec.abs_url or "").strip(),
                "pdf_url": str(rec.pdf_url or "").strip(),
                "comment": str(rec.comment or "").strip(),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": summary_chars,
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    columns = [
        "paper_id",
        "title",
        "summary",
        "authors",
        "categories",
        "primary_category",
        "published",
        "updated",
        "abs_url",
        "pdf_url",
        "comment",
        "authors_joined",
        "categories_joined",
        "summary_chars",
        "age_days",
        "text_for_embedding",
    ]

    if not cleaned_rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(cleaned_rows)
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df


def save_clean_data(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    """Save cleaned DataFrame into CSV and JSON artifacts."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    df_csv = df.copy()
    if "authors" in df_csv.columns:
        df_csv["authors"] = df_csv["authors"].apply(
            lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else x
        )
    if "categories" in df_csv.columns:
        df_csv["categories"] = df_csv["categories"].apply(
            lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else x
        )

    df_csv.to_csv(csv_path, index=False, encoding="utf-8")

    records = df.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

