from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _require_baseline_artifacts(settings) -> None:
    required = {
        "clean dataset": settings.paths.clean_csv,
        "raw records snapshot": settings.paths.raw_records_json,
        "evaluation test set": settings.paths.eval_testset,
        "baseline metrics": settings.paths.baseline_metrics,
    }
    missing = [f"{label}: {path}" for label, path in required.items() if not Path(path).exists()]
    if missing:
        details = "\n".join(f"- {item}" for item in missing)
        raise RuntimeError(f"Baseline artifacts are missing. Run script/run_phase1.py first.\n{details}")


def _save_dataframe(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def main() -> None:
    """Corrupt the baseline, evaluate it, repair from raw data, and compare."""
    settings = load_settings()
    _require_baseline_artifacts(settings)

    baseline_df = pd.read_csv(settings.paths.clean_csv)
    baseline_metrics = read_json(settings.paths.baseline_metrics)

    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    if corrupted_df.empty:
        raise RuntimeError("Corruption produced an empty dataframe.")
    _save_dataframe(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        settings.paths.corrupted_freshness_report,
    )

    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date=now_utc())
    if repaired_df.empty:
        raise RuntimeError("Repair produced an empty dataframe from the raw snapshot.")
    _save_dataframe(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        settings.paths.repaired_freshness_report,
    )
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    print(f"Corrupted metrics: {settings.paths.corrupted_metrics}")
    print(f"Repaired metrics: {settings.paths.repaired_metrics}")
    print(f"Comparison report: {settings.paths.comparison_report}")
