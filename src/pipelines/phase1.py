from __future__ import annotations

import os
from typing import Any

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


def _load_or_fetch_records(settings):
    raw_path = settings.paths.raw_records_json
    if raw_path.exists() and not settings.refresh_source:
        return load_raw_records(raw_path)
    return fetch_source_records(settings)


def _run_agent_demo(settings, index) -> str:
    if os.getenv("RUN_AGENT_DEMO", "").lower() not in {"1", "true", "yes"}:
        return "not requested"

    test_set = read_json(settings.paths.eval_testset)
    agent = build_agent(settings=settings, index=index)
    answers: list[dict[str, Any]] = []
    for item in test_set[:3]:
        answers.append(
            {
                "id": item.get("id"),
                "question": item["question"],
                "answer": run_agent_question(agent, item["question"]),
            }
        )
    write_json(settings.paths.demo_answers, answers)
    return f"PASS ({len(answers)} answers)"


def main() -> None:
    """Run the clean-data baseline pipeline from raw data through reporting."""
    settings = load_settings()
    records = _load_or_fetch_records(settings)
    if not records:
        raise RuntimeError("No raw records available for baseline pipeline.")

    clean_df = build_clean_dataframe(records, run_date=now_utc())
    if clean_df.empty:
        raise RuntimeError("Cleaning produced an empty dataframe for baseline pipeline.")
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )

    if not settings.paths.eval_testset.exists() or settings.refresh_test_set:
        build_test_set(clean_df, settings.paths.eval_testset)

    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, report_name="baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_record_count": len(records),
        "clean_record_count": len(clean_df),
        "refresh_source": settings.refresh_source,
    }
    agent_demo_status = _run_agent_demo(settings, index)
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
        metadata={
            "timestamp_utc": now_utc().isoformat(),
            "llm_provider": settings.llm_provider,
            "llm_model": settings.model_name,
            "embedding_model": settings.embedding_model,
            "collection_name": getattr(index, "collection_name", ""),
            "clean_columns": list(clean_df.columns),
            "agent_demo_status": agent_demo_status,
            "artifact_paths": [str(settings.paths.baseline_metrics), str(settings.paths.baseline_answers)],
        },
    )

    print(f"Raw rows: {len(records)}")
    print(f"Clean rows: {len(clean_df)}")
    print(f"Baseline metrics: {settings.paths.baseline_metrics}")
    print(f"Quality report: {settings.paths.quality_dir}")
    print(f"Baseline report: {settings.paths.baseline_report}")
    if os.getenv("RUN_RAGAS", "").lower() in {"1", "true", "yes"} and bundle.summary.get("ragas", {}).get("status") == "failed":
        raise RuntimeError(f"Ragas evaluation failed: {bundle.summary['ragas'].get('error', 'unknown error')}")
