from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import normalize_whitespace, write_json


def _non_empty(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype(str).str.strip().ne("") & series.astype(str).str.lower().ne("nan")


def _date_series(df: pd.DataFrame) -> pd.Series:
    if "published" not in df:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    return pd.to_datetime(df["published"], errors="coerce", utc=True)


def _content_fingerprint(df: pd.DataFrame) -> pd.Series:
    parts = []
    for column in ("title", "summary", "published", "authors_joined"):
        if column in df:
            values = df[column].fillna("").astype(str).map(normalize_whitespace).str.casefold()
        else:
            values = pd.Series("", index=df.index)
        parts.append(values)
    fingerprint = parts[0]
    for part in parts[1:]:
        fingerprint = fingerprint + "\x1f" + part
    return fingerprint


def _check(name: str, success: bool, observed: Any, expected: Any, **details: Any) -> dict[str, Any]:
    return {
        "name": name,
        "success": bool(success),
        "observed": observed,
        "expected": expected,
        "details": details,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run deterministic quality checks and persist the report artifact."""
    total_rows = len(df)
    threshold = int(getattr(settings, "freshness_threshold_days", 180))
    min_rows = int(getattr(settings, "min_clean_records", 3))
    checks: list[dict[str, Any]] = []

    checks.append(_check(
        "row_count_sufficient", total_rows >= min_rows,
        total_rows, min_rows, description="Minimum clean rows required to build an evaluation set",
    ))

    ids = _non_empty(df["paper_id"]) if "paper_id" in df else pd.Series(False, index=df.index)
    checks.append(_check("paper_id_not_null", int(ids.sum()) == total_rows and total_rows > 0,
                         int(ids.sum()), total_rows))
    unique_ids = int(df.loc[ids, "paper_id"].astype(str).nunique()) if "paper_id" in df else 0
    checks.append(_check("paper_id_unique", unique_ids == total_rows and total_rows > 0,
                         unique_ids, total_rows))

    titles = _non_empty(df["title"]) if "title" in df else pd.Series(False, index=df.index)
    checks.append(_check("title_not_empty", int(titles.sum()) == total_rows and total_rows > 0,
                         int(titles.sum()), total_rows))

    summaries = _non_empty(df["summary"]) if "summary" in df else pd.Series(False, index=df.index)
    summary_lengths = df["summary"].fillna("").astype(str).str.len() if "summary" in df else pd.Series(0, index=df.index)
    min_summary_length = 100
    sufficient = summaries & (summary_lengths >= min_summary_length)
    checks.append(_check("summary_sufficient_length", int(sufficient.sum()) == total_rows and total_rows > 0,
                         int(sufficient.sum()), total_rows, min_required_length=min_summary_length))

    embedding_text = _non_empty(df["text_for_embedding"]) if "text_for_embedding" in df else pd.Series(False, index=df.index)
    checks.append(_check("text_for_embedding_not_empty", int(embedding_text.sum()) == total_rows and total_rows > 0,
                         int(embedding_text.sum()), total_rows))

    duplicate_content = total_rows - int(_content_fingerprint(df).nunique()) if total_rows else 0
    checks.append(_check(
        "no_duplicate_rows", duplicate_content == 0 and total_rows > 0,
        duplicate_content, 0,
        fingerprint="normalized title, summary, published and authors_joined",
    ))

    published = _date_series(df)
    published_valid = published.notna()
    now = pd.Timestamp.now(tz="UTC")
    future_count = int((published > now).fillna(False).sum())
    checks.append(_check(
        "published_date_valid",
        int(published_valid.sum()) == total_rows and future_count == 0 and total_rows > 0,
        int(published_valid.sum()), total_rows, future_dates=future_count,
    ))

    if "age_days" in df:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
        age_valid = ages.notna() & published_valid & (ages >= 0)
    else:
        ages = pd.Series(float("nan"), index=df.index)
        age_valid = pd.Series(False, index=df.index)
    checks.append(_check("age_days_valid", int(age_valid.sum()) == total_rows and total_rows > 0,
                         int(age_valid.sum()), total_rows))

    stale = age_valid & (ages > threshold)
    stale_count = int(stale.sum())
    stale_ratio = round(stale_count / total_rows, 4) if total_rows else 0.0
    checks.append(_check("stale_records_ratio", stale_ratio == 0.0 and total_rows > 0,
                         stale_ratio, 0.0, stale_rows=stale_count, threshold_days=threshold))

    latest_age = int(ages[age_valid].min()) if age_valid.any() else None
    checks.append(_check("latest_pub_date_fresh", latest_age is not None and 0 <= latest_age <= threshold,
                         latest_age, threshold, threshold_days=threshold))

    passed = sum(1 for item in checks if item["success"])
    payload = {
        "report_name": report_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "total_rows": total_rows,
        "total_checks": len(checks),
        "passed_checks": passed,
        "failed_checks": len(checks) - passed,
        "overall_success": passed == len(checks),
        "checks": checks,
    }
    write_json(settings.paths.quality_dir / f"{report_name}.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | str) -> dict[str, Any]:
    """Report valid, future and stale publication dates without string sorting."""
    path = Path(report_path)
    threshold = int(getattr(settings, "freshness_threshold_days", 180))
    dates = _date_series(df)
    valid = dates.notna()
    ages = pd.to_numeric(df["age_days"], errors="coerce") if "age_days" in df else pd.Series(float("nan"), index=df.index)
    age_valid = ages.notna() & valid & (ages >= 0)
    future = int((dates > pd.Timestamp.now(tz="UTC")).fillna(False).sum())
    stale = age_valid & (ages > threshold)
    valid_dates = dates[valid]
    stale_rows = int(stale.sum())
    total_rows = len(df)
    payload = {
        "latest_published": valid_dates.max().date().isoformat() if not valid_dates.empty else "",
        "oldest_published": valid_dates.min().date().isoformat() if not valid_dates.empty else "",
        "invalid_publication_dates": int((~valid).sum()),
        "future_publication_dates": future,
        "invalid_age_days": int((~age_valid).sum()),
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": float(round(stale_rows / total_rows, 4)) if total_rows else 0.0,
        "is_fresh": bool(total_rows > 0 and valid.all() and age_valid.all() and future == 0 and stale_rows == 0),
        "freshness_threshold_days": threshold,
    }
    write_json(path, payload)
    return payload
