from pathlib import Path

from observability.reporting import generate_corruption_report, generate_phase1_report


def test_generate_phase1_report(tmp_path: Path):
    report_file = tmp_path / "phase1_report.md"
    source_summary = {
        "source_api": "Crossref REST API",
        "query": "machine learning",
        "filter": "from-pub-date:2026-01-01",
        "total_fetched": 24,
        "clean_records_count": 24,
    }
    metrics = {
        "retrieval_hit_rate": 0.95,
        "mean_token_f1": 0.85,
        "judge_accuracy": 0.90,
        "mean_judge_score": 4.5,
    }
    quality = {
        "overall_success": True,
        "passed_checks": 9,
        "total_checks": 9,
        "checks": [
            {"name": "paper_id_unique", "success": True, "observed": 24, "expected": 24}
        ],
    }
    freshness = {
        "is_fresh": True,
        "latest_published": "2026-06-01",
        "oldest_published": "2026-01-01",
        "stale_rows": 0,
        "total_rows": 24,
        "stale_ratio": 0.0,
        "freshness_threshold_days": 180,
    }

    generate_phase1_report(report_file, source_summary, metrics, quality, freshness)

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "Baseline Pipeline Report" in content
    assert "0.9500" in content
    assert "paper_id_unique" in content


def test_generate_corruption_report(tmp_path: Path):
    report_file = tmp_path / "corruption_report.md"
    b_metrics = {"retrieval_hit_rate": 0.90, "mean_token_f1": 0.80}
    c_metrics = {"retrieval_hit_rate": 0.50, "mean_token_f1": 0.40}
    r_metrics = {"retrieval_hit_rate": 0.90, "mean_token_f1": 0.80}

    c_quality = {"overall_success": False, "passed_checks": 5, "failed_checks": 4}
    r_quality = {"overall_success": True, "passed_checks": 9, "failed_checks": 0}

    c_freshness = {"is_fresh": False, "latest_published": "2024-01-01", "stale_ratio": 0.5}
    r_freshness = {"is_fresh": True, "latest_published": "2026-06-01", "stale_ratio": 0.0}

    generate_corruption_report(
        report_file,
        b_metrics,
        c_metrics,
        r_metrics,
        c_quality,
        r_quality,
        c_freshness,
        r_freshness,
    )

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "Data Corruption & Pipeline Repair Comparison Report" in content
    assert "-0.4000" in content  # Delta check
    assert "Corrupted Delta" in content
