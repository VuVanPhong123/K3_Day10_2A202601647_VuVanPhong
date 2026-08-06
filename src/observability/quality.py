from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run data quality checks on a DataFrame and save JSON report.

    Checks:
    - row_count_sufficient
    - paper_id_not_null
    - paper_id_unique
    - title_not_empty
    - summary_sufficient_length
    - text_for_embedding_not_empty
    - no_duplicate_rows
    - stale_records_ratio
    - latest_pub_date_fresh
    """
    total_rows = len(df)
    checks: list[dict[str, Any]] = []

    # 1. row_count_sufficient
    expected_rows = getattr(settings, "max_results", 1)
    row_count_success = total_rows >= expected_rows if total_rows > 0 else False
    checks.append(
        {
            "name": "row_count_sufficient",
            "success": row_count_success,
            "observed": total_rows,
            "expected": expected_rows,
            "details": {"description": f"Expected at least {expected_rows} rows"},
        }
    )

    # 2. paper_id_not_null
    paper_id_not_null_cnt = int(df["paper_id"].notna().sum()) if total_rows > 0 and "paper_id" in df.columns else 0
    checks.append(
        {
            "name": "paper_id_not_null",
            "success": paper_id_not_null_cnt == total_rows and total_rows > 0,
            "observed": paper_id_not_null_cnt,
            "expected": total_rows,
            "details": {"null_count": total_rows - paper_id_not_null_cnt},
        }
    )

    # 3. paper_id_unique
    paper_id_unique_cnt = int(df["paper_id"].nunique()) if total_rows > 0 and "paper_id" in df.columns else 0
    checks.append(
        {
            "name": "paper_id_unique",
            "success": paper_id_unique_cnt == total_rows and total_rows > 0,
            "observed": paper_id_unique_cnt,
            "expected": total_rows,
            "details": {"unique_count": paper_id_unique_cnt, "total_rows": total_rows},
        }
    )

    # 4. title_not_empty
    if total_rows > 0 and "title" in df.columns:
        title_valid_cnt = int(df["title"].astype(str).str.strip().ne("").sum())
    else:
        title_valid_cnt = 0
    checks.append(
        {
            "name": "title_not_empty",
            "success": title_valid_cnt == total_rows and total_rows > 0,
            "observed": title_valid_cnt,
            "expected": total_rows,
            "details": {"empty_title_count": total_rows - title_valid_cnt},
        }
    )

    # 5. summary_sufficient_length
    if total_rows > 0 and "summary_chars" in df.columns:
        summary_valid_cnt = int((df["summary_chars"] >= 100).sum())
    elif total_rows > 0 and "summary" in df.columns:
        summary_valid_cnt = int((df["summary"].astype(str).str.len() >= 100).sum())
    else:
        summary_valid_cnt = 0
    checks.append(
        {
            "name": "summary_sufficient_length",
            "success": summary_valid_cnt == total_rows and total_rows > 0,
            "observed": summary_valid_cnt,
            "expected": total_rows,
            "details": {"min_required_length": 100, "valid_count": summary_valid_cnt},
        }
    )

    # 6. text_for_embedding_not_empty
    if total_rows > 0 and "text_for_embedding" in df.columns:
        embed_text_valid_cnt = int(df["text_for_embedding"].astype(str).str.strip().ne("").sum())
    else:
        embed_text_valid_cnt = 0
    checks.append(
        {
            "name": "text_for_embedding_not_empty",
            "success": embed_text_valid_cnt == total_rows and total_rows > 0,
            "observed": embed_text_valid_cnt,
            "expected": total_rows,
            "details": {"empty_count": total_rows - embed_text_valid_cnt},
        }
    )

    # 7. no_duplicate_rows
    if total_rows > 0 and "paper_id" in df.columns:
        duplicate_cnt = int(total_rows - len(df.drop_duplicates(subset=["paper_id"])))
    else:
        duplicate_cnt = 0
    checks.append(
        {
            "name": "no_duplicate_rows",
            "success": duplicate_cnt == 0 and total_rows > 0,
            "observed": duplicate_cnt,
            "expected": 0,
            "details": {"duplicate_row_count": duplicate_cnt},
        }
    )

    # 8. stale_records_ratio
    freshness_threshold = getattr(settings, "freshness_threshold_days", 180)
    if total_rows > 0 and "age_days" in df.columns:
        stale_cnt = int((df["age_days"] > freshness_threshold).sum())
        stale_ratio = round(stale_cnt / total_rows, 4)
    else:
        stale_cnt = total_rows
        stale_ratio = 1.0 if total_rows > 0 else 0.0

    checks.append(
        {
            "name": "stale_records_ratio",
            "success": stale_ratio == 0.0 and total_rows > 0,
            "observed": stale_ratio,
            "expected": 0.0,
            "details": {
                "stale_rows": stale_cnt,
                "total_rows": total_rows,
                "threshold_days": freshness_threshold,
            },
        }
    )

    # 9. latest_pub_date_fresh
    if total_rows > 0 and "age_days" in df.columns:
        min_age_days = int(df["age_days"].min())
    else:
        min_age_days = 9999

    checks.append(
        {
            "name": "latest_pub_date_fresh",
            "success": min_age_days <= freshness_threshold and total_rows > 0,
            "observed": min_age_days,
            "expected": freshness_threshold,
            "details": {"threshold_days": freshness_threshold},
        }
    )

    passed_checks = sum(1 for c in checks if c["success"])
    failed_checks = len(checks) - passed_checks
    overall_success = failed_checks == 0

    report_payload = {
        "report_name": report_name,
        "timestamp": datetime.now(UTC).isoformat(),
        "total_checks": len(checks),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "overall_success": overall_success,
        "checks": checks,
    }

    report_path = settings.paths.quality_dir / f"{report_name}.json"
    write_json(report_path, report_payload)
    return report_payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | str) -> dict[str, Any]:
    """Build freshness report payload and write JSON file."""
    path = Path(report_path) if isinstance(report_path, str) else report_path
    total_rows = len(df)
    threshold_days = getattr(settings, "freshness_threshold_days", 180)

    if total_rows == 0 or "published" not in df.columns:
        latest_published = "N/A"
        oldest_published = "N/A"
        stale_rows = 0
        stale_ratio = 0.0
        is_fresh = False
    else:
        pub_dates = df["published"].astype(str).tolist()
        latest_published = max(pub_dates)
        oldest_published = min(pub_dates)
        if "age_days" in df.columns:
            stale_rows = int((df["age_days"] > threshold_days).sum())
            min_age = int(df["age_days"].min())
        else:
            stale_rows = 0
            min_age = 0
        stale_ratio = round(stale_rows / total_rows, 4)
        is_fresh = (stale_rows == 0) and (min_age <= threshold_days)

    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": int(stale_rows),
        "total_rows": int(total_rows),
        "stale_ratio": float(stale_ratio),
        "is_fresh": bool(is_fresh),
        "freshness_threshold_days": int(threshold_days),
    }

    write_json(path, payload)
    return payload

