from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ingestion.corruption import (
    _add_duplicate_rows,
    _blank_summary,
    _drop_important_docs,
    _inject_noise_summary,
    _stale_publication_date,
    _truncate_title,
    corrupt_clean_dataframe,
)


@pytest.fixture
def clean_dataframe() -> pd.DataFrame:
    rows = []
    run_date = pd.Timestamp("2025-01-01")
    for index in range(12):
        summary = f"A useful abstract for paper {index}."
        published = f"2024-{(index % 9) + 1:02d}-01"
        rows.append(
            {
                "paper_id": f"paper-{index:02d}",
                "title": f"A meaningful research title number {index}",
                "summary": summary,
                "authors_joined": f"Author {index}",
                "categories_joined": "cs.AI, cs.LG",
                "published": published,
                "updated": f"2024-{(index % 9) + 1:02d}-02",
                "age_days": (run_date - pd.Timestamp(published)).days,
                "summary_chars": len(summary),
                "text_for_embedding": summary,
                "abs_url": f"https://example.test/abs/{index}",
                "pdf_url": f"https://example.test/pdf/{index}",
            }
        )
    return pd.DataFrame(rows)


def test_drop_important_docs_prefers_target(clean_dataframe: pd.DataFrame) -> None:
    indexed_dataframe = clean_dataframe.copy(deep=True)
    indexed_dataframe.index = [0, 0, *range(1, 11)]
    result = _drop_important_docs(
        indexed_dataframe,
        {"paper-00", "paper-01"},
        seed=7,
    )

    assert len(result) == len(indexed_dataframe) - 1
    assert set(indexed_dataframe["paper_id"]) - set(result["paper_id"]) <= {
        "paper-00",
        "paper-01",
    }
    assert clean_dataframe["paper_id"].tolist() == [
        f"paper-{index:02d}" for index in range(12)
    ]


def test_blank_summary_sets_empty_string(clean_dataframe: pd.DataFrame) -> None:
    result = _blank_summary(
        clean_dataframe,
        {"paper-00"},
        ratio=1 / 12,
        seed=42,
    )

    assert result.loc[result["paper_id"] == "paper-00", "summary"].iloc[0] == ""


def test_inject_noise_summary_keeps_original_content(
    clean_dataframe: pd.DataFrame,
) -> None:
    blanked = _blank_summary(clean_dataframe, ratio=1 / 12, seed=42)
    blank_ids = set(blanked.loc[blanked["summary"] == "", "paper_id"])
    result = _inject_noise_summary(
        blanked,
        ratio=1,
        seed=42,
        excluded_paper_ids=blank_ids,
    )

    assert blank_ids
    assert all(
        result.loc[result["paper_id"] == paper_id, "summary"].iloc[0] == ""
        for paper_id in blank_ids
    )
    noisy = result.loc[~result["paper_id"].isin(blank_ids), "summary"]
    assert noisy.str.contains("CORRUPTION_NOISE_").all()
    assert noisy.str.len().min() > 16


def test_truncate_title_keeps_non_empty_prefix(
    clean_dataframe: pd.DataFrame,
) -> None:
    result = _truncate_title(clean_dataframe, ratio=1, length=10, seed=42)

    assert result["title"].str.len().eq(10).all()
    assert result["title"].ne("").all()
    assert result.loc[0, "title"] == clean_dataframe.loc[0, "title"][:10]


def test_stale_publication_date_moves_dates_back(
    clean_dataframe: pd.DataFrame,
) -> None:
    result = _stale_publication_date(clean_dataframe, ratio=1, seed=42)

    original_dates = pd.to_datetime(clean_dataframe["published"])
    stale_dates = pd.to_datetime(result["published"])
    assert (stale_dates < original_dates).all()
    assert ((original_dates - stale_dates).dt.days >= 1095).all()
    assert (pd.to_datetime(result["updated"]) < pd.to_datetime(clean_dataframe["updated"])).all()


def test_add_duplicate_rows_adds_at_least_two_rows(
    clean_dataframe: pd.DataFrame,
) -> None:
    result = _add_duplicate_rows(clean_dataframe.iloc[:1], {"paper-00"}, seed=42)

    assert len(result) == 3
    assert result["paper_id"].str.contains(r"-dup(?:-\d+)?$").sum() == 2
    base_paper_ids = result["paper_id"].str.replace(
        r"-dup(?:-\d+)?$",
        "",
        regex=True,
    )
    assert base_paper_ids.duplicated().any()


def test_add_duplicate_rows_respects_zero_ratio(
    clean_dataframe: pd.DataFrame,
) -> None:
    result = _add_duplicate_rows(clean_dataframe, ratio=0, seed=42)

    pd.testing.assert_frame_equal(result, clean_dataframe)


def test_corrupt_clean_dataframe_is_deterministic(
    clean_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    first_log = tmp_path / "first.json"
    second_log = tmp_path / "second.json"
    targets = {"paper-00", "paper-01", "paper-02"}

    first = corrupt_clean_dataframe(clean_dataframe, first_log, targets, seed=123)
    second = corrupt_clean_dataframe(clean_dataframe, second_log, targets, seed=123)

    pd.testing.assert_frame_equal(first, second)
    assert json.loads(first_log.read_text(encoding="utf-8")) == json.loads(
        second_log.read_text(encoding="utf-8")
    )
    expected_age_days = (
        pd.Timestamp("2025-01-01") - pd.to_datetime(first["published"])
    ).dt.days
    pd.testing.assert_series_equal(
        first["age_days"],
        expected_age_days.rename("age_days"),
    )


def test_corrupt_clean_dataframe_does_not_mutate_input(
    clean_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    original = clean_dataframe.copy(deep=True)
    corrupt_clean_dataframe(clean_dataframe, tmp_path / "corruption.json", seed=42)

    pd.testing.assert_frame_equal(clean_dataframe, original)


def test_target_doc_ids_corrupted_before_random_rows(
    clean_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    targets = {"paper-00", "paper-01", "paper-02"}
    corrupt_clean_dataframe(
        clean_dataframe,
        tmp_path / "corruption.json",
        target_doc_ids=targets,
        seed=42,
    )
    records = json.loads((tmp_path / "corruption.json").read_text(encoding="utf-8"))

    records_by_scenario = {record["scenario"]: record for record in records}
    for scenario in (
        "drop_important_docs",
        "blank_summary",
        "truncate_title",
        "stale_publication_date",
        "add_duplicate_rows",
    ):
        affected = records_by_scenario[scenario]["affected_paper_ids"]
        assert any(paper_id in targets for paper_id in affected)

    for record in records[:-1]:
        affected = record["affected_paper_ids"]
        target_positions = [index for index, paper_id in enumerate(affected) if paper_id in targets]
        other_positions = [index for index, paper_id in enumerate(affected) if paper_id not in targets]
        if target_positions and other_positions:
            assert max(target_positions) < min(other_positions)


def test_corruption_log_has_required_schema_and_quality_failure(
    clean_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "nested" / "corruption.json"
    result = corrupt_clean_dataframe(clean_dataframe, log_path, seed=42)
    records = json.loads(log_path.read_text(encoding="utf-8"))

    assert len(records) == 7
    assert records[-1]["scenario"] == "summary"
    assert records[-1]["row_count_before"] == len(clean_dataframe)
    assert records[-1]["row_count_after"] == len(result)
    for record in records:
        assert {
            "scenario",
            "seed",
            "row_count_before",
            "row_count_after",
            "affected_paper_ids",
            "fields_changed",
        }.issubset(record)
    for record in records[:-1]:
        assert {"before", "after"}.issubset(record)
    assert (result["summary"] == "").any()
    assert (result["summary_chars"] == result["summary"].str.len()).all()
    assert result.loc[0, "text_for_embedding"].startswith("Title:")
