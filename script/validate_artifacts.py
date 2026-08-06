"""Validate the reproducible artifacts produced by the Day 10 lab."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_ARTIFACTS = (
    "data/raw/crossref_response.json",
    "data/raw/crossref_records.json",
    "data/clean/papers_clean.csv",
    "data/clean/papers_clean.json",
    "data/embeddings/papers_embeddings.json",
    "data/eval/test_set.json",
    "data/results/baseline_metrics.json",
    "data/results/baseline_answers.json",
    "data/results/agent_demo_answers.json",
    "data/quality/baseline.json",
    "data/quality/freshness_report.json",
    "data/reports/phase1_report.md",
    "data/clean/papers_clean_corrupted.csv",
    "data/clean/papers_clean_corrupted.json",
    "data/embeddings/papers_embeddings_corrupted.json",
    "data/clean/papers_clean_repaired.csv",
    "data/clean/papers_clean_repaired.json",
    "data/embeddings/papers_embeddings_repaired.json",
    "data/results/corruption_log.json",
    "data/results/corrupted_metrics.json",
    "data/results/corrupted_answers.json",
    "data/results/repaired_metrics.json",
    "data/results/repaired_answers.json",
    "data/quality/corrupted.json",
    "data/quality/freshness_corrupted.json",
    "data/quality/repaired.json",
    "data/quality/freshness_repaired.json",
    "data/reports/corruption_report.md",
    "data/reports/final_lab_report.md",
)


def _assert_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Non-finite JSON value at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_finite(item, f"{path}.{key}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite(item, f"{path}[{index}]")


def _read_json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    _assert_finite(value, str(path))
    return value


def validate(project_dir: Path) -> None:
    missing = [relative for relative in REQUIRED_ARTIFACTS if not (project_dir / relative).is_file()]
    if missing:
        raise FileNotFoundError("Missing artifacts: " + ", ".join(missing))

    for relative in REQUIRED_ARTIFACTS:
        path = project_dir / relative
        if path.suffix == ".json":
            _read_json(path)
        elif path.suffix == ".csv":
            pd.read_csv(path, keep_default_na=False)
        elif not path.read_text(encoding="utf-8").strip():
            raise ValueError(f"Empty Markdown artifact: {relative}")

    baseline_clean = pd.read_csv(project_dir / "data/clean/papers_clean.csv", keep_default_na=False)
    test_set = _read_json(project_dir / "data/eval/test_set.json")
    clean_ids = set(baseline_clean["paper_id"].astype(str))
    truth_ids = {str(doc_id) for item in test_set for doc_id in item.get("ground_truth_doc_ids", [])}
    if not truth_ids or not truth_ids.issubset(clean_ids):
        raise ValueError("Evaluation ground-truth IDs are not present in the baseline clean data")

    for state in ("baseline", "corrupted", "repaired"):
        metrics = _read_json(project_dir / f"data/results/{state}_metrics.json")
        answers = _read_json(project_dir / f"data/results/{state}_answers.json")
        if int(metrics.get("samples", -1)) != len(answers):
            raise ValueError(f"{state} metrics sample count does not match answers")

    corruption_log = _read_json(project_dir / "data/results/corruption_log.json")
    affected_ids = {str(doc_id) for item in corruption_log for doc_id in item.get("affected_paper_ids", [])}
    if not affected_ids:
        raise ValueError("Corruption log has no affected document IDs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    validate(args.project_dir.resolve())
    print("Artifact validation passed.")


if __name__ == "__main__":
    main()
