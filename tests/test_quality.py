from pathlib import Path
import pandas as pd

from core.config import load_settings
from observability.quality import build_freshness_report, run_data_quality_checks


def test_run_data_quality_checks(tmp_path: Path):
    settings = load_settings(project_dir=tmp_path)

    # Synthetic clean dataframe
    clean_data = [
        {
            "paper_id": f"10.1000/p{i}",
            "title": f"Title {i}",
            "summary": "Sample summary text that is long enough to satisfy the 100 character length constraint required for data quality check.",
            "summary_chars": 120,
            "text_for_embedding": f"Title {i} | Summary text",
            "published": "2026-06-01",
            "age_days": 10,
        }
        for i in range(24)
    ]
    df_clean = pd.DataFrame(clean_data)

    report = run_data_quality_checks(df_clean, settings, "test_baseline_quality")
    assert report["overall_success"] is True
    assert report["passed_checks"] == 11
    assert report["failed_checks"] == 0

    # Synthetic corrupted dataframe with duplicates & short summary
    corrupted_data = list(clean_data)
    corrupted_data[0]["summary_chars"] = 20  # Short summary
    corrupted_data[1]["paper_id"] = corrupted_data[0]["paper_id"]  # Duplicate paper_id
    df_corrupted = pd.DataFrame(corrupted_data)

    report_corrupted = run_data_quality_checks(df_corrupted, settings, "test_corrupted_quality")
    assert report_corrupted["overall_success"] is False
    assert report_corrupted["failed_checks"] > 0


def test_build_freshness_report(tmp_path: Path):
    settings = load_settings(project_dir=tmp_path)
    df_fresh = pd.DataFrame(
        [
            {"published": "2026-06-01", "age_days": 20},
            {"published": "2026-05-15", "age_days": 35},
        ]
    )

    report_path = tmp_path / "freshness.json"
    freshness = build_freshness_report(df_fresh, settings, report_path)

    assert freshness["is_fresh"] is True
    assert freshness["latest_published"] == "2026-06-01"
    assert freshness["stale_rows"] == 0
    assert report_path.exists()


def test_invalid_date_is_not_fresh_and_content_duplicate_fails(tmp_path: Path):
    settings = load_settings(project_dir=tmp_path)
    summary = "A sufficiently long abstract " * 8
    frame = pd.DataFrame([
        {"paper_id": "p1", "title": "Same", "summary": summary, "published": "not-a-date", "age_days": -1, "summary_chars": len(summary), "text_for_embedding": "x"},
        {"paper_id": "p2", "title": "Same", "summary": summary, "published": "2026-06-01", "age_days": 10, "summary_chars": len(summary), "text_for_embedding": "x"},
        {"paper_id": "p3", "title": "Same", "summary": summary, "published": "2026-06-01", "age_days": 10, "summary_chars": len(summary), "text_for_embedding": "x"},
    ])
    quality = run_data_quality_checks(frame, settings, "invalid_date")
    names = {check["name"]: check for check in quality["checks"]}
    assert not names["published_date_valid"]["success"]
    assert not names["age_days_valid"]["success"]
    assert not names["no_duplicate_rows"]["success"]

    freshness = build_freshness_report(frame, settings, tmp_path / "freshness.json")
    assert freshness["invalid_publication_dates"] == 1
    assert freshness["is_fresh"] is False
