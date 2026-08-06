from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import write_text


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _source_value(source: dict[str, Any], canonical: str, legacy: str) -> Any:
    return source.get(canonical, source.get(legacy, ""))


def _status(success: bool) -> str:
    return "PASS" if success else "FAIL"


def generate_phase1_report(
    report_path: Path | str,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Generate a baseline report from the actual pipeline artifacts."""
    metadata = metadata or {}
    lines = [
        "# Baseline Pipeline Report (Phase 1)",
        "",
        "## Run Metadata",
        f"- Timestamp (UTC): `{metadata.get('timestamp_utc', '')}`",
        f"- LLM provider/model: `{metadata.get('llm_provider', '')}` / `{metadata.get('llm_model', '')}`",
        f"- Embedding model: `{metadata.get('embedding_model', '')}`",
        f"- Chroma collection: `{metadata.get('collection_name', '')}`",
        "",
        "## Source Summary",
        f"- Source API: `{source_summary.get('source_api', '')}`",
        f"- Query: `{_source_value(source_summary, 'source_query', 'query')}`",
        f"- Filter: `{_source_value(source_summary, 'source_filter', 'filter')}`",
        f"- Raw row count: `{_source_value(source_summary, 'raw_record_count', 'total_fetched')}`",
        f"- Clean row count: `{_source_value(source_summary, 'clean_record_count', 'clean_records_count')}`",
        "",
        "## Clean Schema",
        f"`{', '.join(metadata.get('clean_columns', []))}`",
        "",
        "## Evaluation Metrics",
        "| Metric | Value |",
        "| :--- | ---: |",
    ]
    for key, value in metrics.items():
        if isinstance(value, (int, float, str, bool)):
            lines.append(f"| `{key}` | `{_fmt(value)}` |")
    lines += [
        "",
        "## LLM Judge",
        f"- Provider/model: `{metrics.get('judge_provider', metadata.get('llm_provider', ''))}` / `{metrics.get('judge_model', metadata.get('llm_model', ''))}`",
        f"- Successful LLM judgments: `{metrics.get('llm_judge_success_count', 0)}`",
        f"- Heuristic fallbacks: `{metrics.get('llm_judge_fallback_count', 0)}`",
        "",
        "## Ragas",
        f"`{metrics.get('ragas', {})}`",
        "",
        "## Data Quality",
        f"- Status: `{_status(bool(quality.get('overall_success')))}`",
        f"- Passed/total: `{quality.get('passed_checks', 0)}/{quality.get('total_checks', 0)}`",
        "",
        "| Check | Status | Observed | Expected |",
        "| :--- | :--- | ---: | ---: |",
    ]
    for check in quality.get("checks", []):
        lines.append(
            f"| `{check.get('name', '')}` | `{_status(bool(check.get('success')))}` | "
            f"`{_fmt(check.get('observed'))}` | `{_fmt(check.get('expected'))}` |"
        )
    lines += [
        "",
        "## Freshness",
        f"- Status: `{_status(bool(freshness.get('is_fresh')))}`",
        f"- Latest/oldest valid publication: `{freshness.get('latest_published', '')}` / `{freshness.get('oldest_published', '')}`",
        f"- Invalid/future dates: `{freshness.get('invalid_publication_dates', 0)}/{freshness.get('future_publication_dates', 0)}`",
        f"- Stale ratio: `{_fmt(freshness.get('stale_ratio', 0.0))}`",
        "",
        "## Agent Demo",
        f"- Status: `{metadata.get('agent_demo_status', 'not requested')}`",
        "",
        "## Artifact Paths",
    ]
    for path in metadata.get("artifact_paths", []):
        lines.append(f"- `{path}`")
    lines += [
        "",
        "## Limitations",
        "- LLM judge and agent demo require the selected provider credentials when enabled.",
        "- Ragas is optional and is reported separately from the core retrieval metrics.",
    ]
    write_text(Path(report_path), "\n".join(lines) + "\n")


def _numeric_delta(baseline: Any, value: Any) -> str:
    if isinstance(baseline, (int, float)) and isinstance(value, (int, float)):
        return f"{value - baseline:+.4f}"
    return ""


def generate_corruption_report(
    report_path: Path | str,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    corruption_log: list[dict[str, Any]] | None = None,
) -> None:
    """Generate a three-state comparison report with metric-derived findings."""
    baseline_quality = baseline_quality or {}
    baseline_freshness = baseline_freshness or {}
    corruption_log = corruption_log or []
    keys = list(dict.fromkeys((*baseline_metrics.keys(), *corrupted_metrics.keys(), *repaired_metrics.keys())))
    lines = [
        "# Data Corruption & Pipeline Repair Comparison Report",
        "",
        "## Corruption Scenarios",
        f"- Scenarios recorded: `{len(corruption_log)}`",
        f"- Affected document IDs: `{len({doc_id for item in corruption_log for doc_id in item.get('affected_paper_ids', [])})}`",
        "",
        "## Metrics Comparison (Corrupted Delta and Repaired Delta)",
        "| Metric | Baseline | Corrupted | Repaired | Corrupted Δ | Repaired Δ |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in keys:
        lines.append(
            f"| `{key}` | `{_fmt(baseline_metrics.get(key))}` | `{_fmt(corrupted_metrics.get(key))}` | "
            f"`{_fmt(repaired_metrics.get(key))}` | `{_numeric_delta(baseline_metrics.get(key), corrupted_metrics.get(key))}` | "
            f"`{_numeric_delta(baseline_metrics.get(key), repaired_metrics.get(key))}` |"
        )
    lines += [
        "",
        "## Data Quality Comparison",
        "| State | Status | Passed | Failed | Rows |",
        "| :--- | :--- | ---: | ---: | ---: |",
    ]
    for name, payload in (("Baseline", baseline_quality), ("Corrupted", corrupted_quality), ("Repaired", repaired_quality)):
        lines.append(f"| **{name}** | `{_status(bool(payload.get('overall_success')))}` | `{payload.get('passed_checks', 0)}` | `{payload.get('failed_checks', 0)}` | `{payload.get('total_rows', '')}` |")
    lines += [
        "",
        "## Freshness Comparison",
        "| State | Status | Latest | Stale ratio | Invalid dates |",
        "| :--- | :--- | :--- | ---: | ---: |",
    ]
    for name, payload in (("Baseline", baseline_freshness), ("Corrupted", corrupted_freshness), ("Repaired", repaired_freshness)):
        lines.append(f"| **{name}** | `{_status(bool(payload.get('is_fresh')))}` | `{payload.get('latest_published', '')}` | `{_fmt(payload.get('stale_ratio', 0.0))}` | `{payload.get('invalid_publication_dates', 0)}` |")

    degraded = [
        key for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")
        if isinstance(baseline_metrics.get(key), (int, float))
        and isinstance(corrupted_metrics.get(key), (int, float))
        and corrupted_metrics[key] < baseline_metrics[key]
    ]
    recovered = [
        key for key in degraded
        if isinstance(repaired_metrics.get(key), (int, float))
        and repaired_metrics[key] > corrupted_metrics[key]
    ]
    lines += ["", "## Evidence-based Conclusion"]
    if degraded:
        lines.append(f"- Corruption reduced: `{', '.join(degraded)}`.")
    else:
        lines.append("- No requested retrieval/answer/judge metric decreased in this run.")
    if recovered:
        lines.append(f"- Repair improved over corrupted for: `{', '.join(recovered)}`.")
    else:
        lines.append("- Repair did not improve a measured degraded metric in this run.")
    lines.append(f"- Quality status: baseline `{_status(bool(baseline_quality.get('overall_success')))}`, corrupted `{_status(bool(corrupted_quality.get('overall_success')))}`, repaired `{_status(bool(repaired_quality.get('overall_success')))}`.")
    lines.append("- Repair input was the raw-record snapshot and the clean transformation was rerun.")
    write_text(Path(report_path), "\n".join(lines) + "\n")


def generate_final_lab_report(report_path: Path | str, artifacts: dict[str, Any]) -> None:
    """Write the final lab report from already-loaded artifact data."""
    baseline = artifacts.get("baseline_metrics", {})
    corrupted = artifacts.get("corrupted_metrics", {})
    repaired = artifacts.get("repaired_metrics", {})
    lines = [
        "# Final Lab Report: Data Pipeline and Data Observability",
        "",
        "## Team Information",
        "> Pending: team member names and assignments will be supplied later.",
        "",
        "## Lab Objective",
        "Build, observe, corrupt, repair and evaluate a Crossref-backed RAG corpus.",
        "",
        "## System Architecture",
        "```mermaid",
        "flowchart LR",
        " A[Crossref API] --> B[Raw Snapshot] --> C[Cleaning] --> D[MiniLM Embeddings] --> E[ChromaDB]",
        " C --> F[Quality and Freshness]",
        " E --> G[RAG Evaluation]",
        " C --> H[Corruption] --> I[Corrupted Evaluation]",
        " B --> J[Repair from Raw] --> K[Repaired Evaluation]",
        " G --> L[Comparison Report]; I --> L; K --> L",
        "```",
        "",
        "## Data Lineage",
        "Crossref response → parsed raw records → clean contract → local MiniLM/Chroma index → evaluation and observability artifacts.",
        "",
        "## Source, Cleaning and Retrieval",
        f"- Source: `{artifacts.get('source_summary', {})}`",
        f"- Clean rows: `{artifacts.get('clean_rows', '')}`; test-set samples: `{artifacts.get('test_set_size', '')}`",
        f"- Embedding model: `{artifacts.get('embedding_model', '')}`",
        "- RAG answers use the same evaluation set for baseline, corrupted and repaired states.",
        "",
        "## Evaluation Methodology",
        "Retrieval hit rate, token F1, LLM judge accuracy/score, data quality checks and freshness are compared across three states.",
        "",
        "## Baseline Results",
        f"`{baseline}`",
        "",
        "## Corruption and Repair Results",
        f"- Corrupted: `{corrupted}`",
        f"- Repaired: `{repaired}`",
        f"- Quality: `{artifacts.get('quality_comparison', {})}`",
        f"- Freshness: `{artifacts.get('freshness_comparison', {})}`",
        "",
        "## Reproducibility and Artifact Inventory",
        "Run `uv sync --extra dev`, configure `.env`, run baseline first, then run corruption flow. Raw snapshots are retained so repair does not copy the baseline clean CSV.",
        "",
    ]
    for item in artifacts.get("artifact_paths", []):
        lines.append(f"- `{item}`")
    lines += [
        "",
        "## Known Limitations",
        "Provider availability, model nondeterminism and optional Ragas compatibility can affect LLM metrics.",
        "",
        "## Final Conclusion",
        "The conclusion is intentionally derived from the recorded baseline, corrupted and repaired artifacts; no fixed recovery percentage is asserted.",
    ]
    write_text(Path(report_path), "\n".join(lines) + "\n")
