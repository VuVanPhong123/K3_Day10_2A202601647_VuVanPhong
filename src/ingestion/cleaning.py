from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a DataFrame ready for embedding.

    Pipeline:
    1. Convert to DataFrame.
    2. Normalize whitespace in title, summary.
    3. Join authors and categories.
    4. Parse dates and calculate age_days.
    5. Create text_for_embedding and summary_chars.
    6. Filter invalid rows (missing/empty title, summary, paper_id).
    7. Remove duplicates (by paper_id, keep first).
    8. Sort deterministically.
    """
    if not records:
        return pd.DataFrame(
            columns=[
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
        )

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

    from core.utils import compact_join, normalize_whitespace

    df["title"] = df["title"].fillna("").apply(normalize_whitespace)
    df["summary"] = df["summary"].fillna("").apply(normalize_whitespace)
    df["authors_joined"] = df["authors"].apply(
        lambda x: compact_join(x) if isinstance(x, list) else ""
    )
    df["categories_joined"] = df["categories"].apply(
        lambda x: compact_join(x) if isinstance(x, list) else ""
    )

    df["published"] = df["published"].fillna("")
    df["updated"] = df["updated"].fillna("")

    def calc_age_days(pub_str: str) -> int:
        if not pub_str:
            return -1
        try:
            pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            return (run_date - pub_date).days
        except Exception:
            return -1

    df["age_days"] = df["published"].apply(calc_age_days)
    df["summary_chars"] = df["summary"].apply(len)

    df["text_for_embedding"] = df.apply(
        lambda row: f"{row['title']} {row['summary']} {row['authors_joined']} {row['categories_joined']}",
        axis=1,
    )
    df["text_for_embedding"] = df["text_for_embedding"].apply(normalize_whitespace)

    df = df[
        (df["paper_id"].notna())
        & (df["paper_id"] != "")
        & (df["title"] != "")
        & (df["summary"] != "")
        & (df["text_for_embedding"] != "")
    ].copy()

    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)

    columns_ordered = [
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
    df = df[columns_ordered]

    return df
