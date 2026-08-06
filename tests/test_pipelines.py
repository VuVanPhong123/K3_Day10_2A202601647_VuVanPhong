from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pandas as pd
import pytest

from core.config import load_settings
from core.utils import write_json
import pipelines.corruption_flow as corruption_flow
import pipelines.phase1 as phase1


def _settings(tmp_path, **overrides):
    return replace(load_settings(project_dir=tmp_path), **overrides)


def _patch_phase1(monkeypatch, settings, *, records, clean_df, testset_calls, calls):
    monkeypatch.setattr(phase1, "load_settings", lambda: settings)
    monkeypatch.setattr(phase1, "load_raw_records", lambda path: calls.append(("load", path)) or records)
    monkeypatch.setattr(
        phase1,
        "fetch_source_records",
        lambda current_settings: calls.append(("fetch", current_settings)) or records,
    )
    monkeypatch.setattr(phase1, "build_clean_dataframe", lambda current_records, run_date: clean_df)
    monkeypatch.setattr(
        phase1,
        "LocalEmbeddingIndex",
        SimpleNamespace(build=lambda df, settings, embeddings_output_path: calls.append(("index", embeddings_output_path)) or object()),
    )

    def fake_build_test_set(df, path):
        testset_calls.append(path)
        write_json(path, [{"id": "q1", "question": "test"}])

    monkeypatch.setattr(phase1, "build_test_set", fake_build_test_set)
    monkeypatch.setattr(
        phase1,
        "evaluate_pipeline",
        lambda settings, index, test_set_path, metrics_output_path, answers_output_path: calls.append(
            ("evaluate", test_set_path, metrics_output_path, answers_output_path)
        )
        or SimpleNamespace(summary={"retrieval_hit_rate": 1.0}),
    )
    monkeypatch.setattr(
        phase1,
        "run_data_quality_checks",
        lambda df, settings, report_name: calls.append(("quality", report_name)) or {"success": True},
    )
    monkeypatch.setattr(
        phase1,
        "build_freshness_report",
        lambda df, settings, report_path: calls.append(("freshness", report_path)) or {"is_fresh": True},
    )
    monkeypatch.setattr(
        phase1,
        "generate_phase1_report",
        lambda **kwargs: calls.append(("report", kwargs)),
    )
    monkeypatch.setattr(phase1, "build_agent", lambda **kwargs: pytest.fail("agent demo must be disabled"))


def test_phase1_reuses_raw_snapshot_and_builds_missing_test_set(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.raw_records_json.write_text("[]", encoding="utf-8")
    clean_df = pd.DataFrame([{"paper_id": "p1", "title": "Title", "summary": "Summary"}])
    calls = []
    testset_calls = []
    _patch_phase1(monkeypatch, settings, records=["cached"], clean_df=clean_df, testset_calls=testset_calls, calls=calls)

    phase1.main()

    assert any(call[0] == "load" for call in calls)
    assert not any(call[0] == "fetch" for call in calls)
    assert testset_calls == [settings.paths.eval_testset]
    evaluate_call = next(call for call in calls if call[0] == "evaluate")
    assert evaluate_call[1:] == (
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    assert settings.paths.clean_csv.exists()
    assert settings.paths.clean_json.exists()


def test_phase1_fetches_when_snapshot_missing_and_rebuilds_test_set_on_refresh(monkeypatch, tmp_path):
    settings = _settings(tmp_path, refresh_source=False, refresh_test_set=True)
    settings.paths.eval_testset.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.eval_testset.write_text("[]", encoding="utf-8")
    clean_df = pd.DataFrame([{"paper_id": "p1", "title": "Title", "summary": "Summary"}])
    calls = []
    testset_calls = []
    _patch_phase1(monkeypatch, settings, records=["fetched"], clean_df=clean_df, testset_calls=testset_calls, calls=calls)

    phase1.main()

    assert any(call[0] == "fetch" for call in calls)
    assert not any(call[0] == "load" for call in calls)
    assert testset_calls == [settings.paths.eval_testset]


def _prepare_corruption_prerequisites(settings):
    baseline_df = pd.DataFrame([{"paper_id": "p1", "title": "Baseline", "summary": "clean"}])
    settings.paths.clean_csv.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.clean_csv.write_text(baseline_df.to_csv(index=False), encoding="utf-8")
    write_json(settings.paths.raw_records_json, [{"paper_id": "raw"}])
    write_json(settings.paths.eval_testset, [{"id": "q1", "question": "test"}])
    write_json(settings.paths.baseline_metrics, {"retrieval_hit_rate": 1.0})
    return baseline_df


def test_corruption_flow_requires_baseline_artifacts(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    monkeypatch.setattr(corruption_flow, "load_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="Baseline artifacts are missing"):
        corruption_flow.main()


def test_corruption_flow_reuses_test_set_and_repairs_from_raw(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    _prepare_corruption_prerequisites(settings)
    corrupted_df = pd.DataFrame([{"paper_id": "p1", "title": "Corrupted", "summary": "noise"}])
    repaired_df = pd.DataFrame([{"paper_id": "p1", "title": "Repaired", "summary": "clean"}])
    calls = []
    monkeypatch.setattr(corruption_flow, "load_settings", lambda: settings)
    monkeypatch.setattr(
        corruption_flow,
        "corrupt_clean_dataframe",
        lambda df, path: calls.append(("corrupt", path)) or corrupted_df,
    )
    monkeypatch.setattr(
        corruption_flow,
        "load_raw_records",
        lambda path: calls.append(("load_raw", path)) or ["raw-record"],
    )
    monkeypatch.setattr(
        corruption_flow,
        "build_clean_dataframe",
        lambda records, run_date: calls.append(("repair_clean", records)) or repaired_df,
    )
    monkeypatch.setattr(
        corruption_flow,
        "LocalEmbeddingIndex",
        SimpleNamespace(
            build=lambda df, settings, embeddings_output_path: calls.append(("index", df, embeddings_output_path)) or object()
        ),
    )

    def fake_evaluate(settings, index, test_set_path, metrics_output_path, answers_output_path):
        calls.append(("evaluate", test_set_path, metrics_output_path, answers_output_path))
        return SimpleNamespace(summary={"retrieval_hit_rate": 0.5})

    monkeypatch.setattr(corruption_flow, "evaluate_pipeline", fake_evaluate)
    monkeypatch.setattr(
        corruption_flow,
        "run_data_quality_checks",
        lambda df, settings, report_name: calls.append(("quality", report_name)) or {"report_name": report_name},
    )
    monkeypatch.setattr(
        corruption_flow,
        "build_freshness_report",
        lambda df, settings, report_path: calls.append(("freshness", report_path)) or {"path": str(report_path)},
    )
    monkeypatch.setattr(
        corruption_flow,
        "generate_corruption_report",
        lambda **kwargs: calls.append(("report", kwargs)),
    )

    corruption_flow.main()

    index_calls = [call for call in calls if call[0] == "index"]
    assert index_calls[0][2] == settings.paths.corrupted_embeddings_json
    assert index_calls[1][2] == settings.paths.repaired_embeddings_json
    evaluate_calls = [call for call in calls if call[0] == "evaluate"]
    assert len(evaluate_calls) == 2
    assert evaluate_calls[0][1] == settings.paths.eval_testset
    assert evaluate_calls[1][1] == settings.paths.eval_testset
    assert any(call[0] == "load_raw" for call in calls)
    assert any(call[0] == "repair_clean" for call in calls)
    assert ("quality", "corrupted") in calls
    assert ("quality", "repaired") in calls
    assert any(call[0] == "report" for call in calls)
    assert settings.paths.corrupted_clean_csv.exists()
    assert settings.paths.repaired_clean_json.exists()
    freshness_paths = [call[1] for call in calls if call[0] == "freshness"]
    assert freshness_paths == [
        settings.paths.corrupted_freshness_report,
        settings.paths.repaired_freshness_report,
    ]
