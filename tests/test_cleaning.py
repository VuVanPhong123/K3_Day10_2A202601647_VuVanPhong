from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from ingestion.cleaning import CLEAN_COLUMNS, build_clean_dataframe


def test_returns_contract_columns(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    assert list(df.columns) == CLEAN_COLUMNS


def test_empty_input_keeps_contract(run_date):
    df = build_clean_dataframe([], run_date)
    assert df.empty
    assert list(df.columns) == CLEAN_COLUMNS
    assert df["age_days"].dtype == "int64"
    assert df["summary_chars"].dtype == "int64"


def test_drops_rows_without_title_or_summary(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    kept = set(df["paper_id"])
    assert "doi_2024_006" not in kept  # empty title
    assert "doi_2024_007" not in kept  # empty summary


def test_drops_duplicate_title(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    assert df["title"].str.lower().duplicated().sum() == 0
    assert "doi_2024_005" not in set(df["paper_id"])
    assert "doi_2024_001" in set(df["paper_id"])


def test_drops_duplicate_paper_id(sample_paper_records, run_date):
    duplicate = replace(
        sample_paper_records[0],
        title="A Different Title That Does Not Collide",
        summary="A different summary body.",
    )
    df = build_clean_dataframe([sample_paper_records[0], duplicate], run_date)
    assert len(df) == 1
    assert df.iloc[0]["title"] == sample_paper_records[0].title


def test_normalizes_whitespace(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    row = df[df["paper_id"] == "doi_2024_004"].iloc[0]
    assert row["summary"] == row["summary"].strip()
    assert "  " not in row["summary"]


def test_joins_authors_and_categories(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    row = df[df["paper_id"] == "doi_2024_001"].iloc[0]
    assert row["authors_joined"] == "Alice Smith, Bob Johnson"
    assert row["categories_joined"] == "Computer Science, Machine Learning"


def test_age_days_uses_run_date(run_date, sample_paper_records):
    df = build_clean_dataframe(sample_paper_records, run_date)
    row = df[df["paper_id"] == "doi_2024_001"].iloc[0]
    expected = (run_date - datetime(2024, 1, 15, tzinfo=UTC)).days
    assert row["age_days"] == expected


def test_dates_normalized_to_iso(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    for column in ("published", "updated"):
        for value in df[column]:
            datetime.fromisoformat(value)
            assert len(value) == len("2024-01-15")


def test_summary_chars_matches_summary(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    assert (df["summary_chars"] == df["summary"].str.len()).all()


def test_text_for_embedding_contains_all_parts(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    row = df[df["paper_id"] == "doi_2024_001"].iloc[0]
    text = row["text_for_embedding"]
    assert row["title"] in text
    assert row["summary"] in text
    assert row["authors_joined"] in text
    assert row["categories_joined"] in text
    assert text == text.strip()


def test_sorted_by_published_desc_then_paper_id(sample_paper_records, run_date):
    df = build_clean_dataframe(sample_paper_records, run_date)
    published = df["published"].tolist()
    assert published == sorted(published, reverse=True)
    # Ties on `published` fall back to ascending paper_id.
    for i in range(len(df) - 1):
        if published[i] == published[i + 1]:
            assert df["paper_id"][i] < df["paper_id"][i + 1]


def test_deterministic_across_runs(sample_paper_records, run_date):
    first = build_clean_dataframe(sample_paper_records, run_date)
    second = build_clean_dataframe(sample_paper_records, run_date)
    assert first["paper_id"].tolist() == second["paper_id"].tolist()
    assert first.equals(second)


def test_row_order_independent_of_input_order(sample_paper_records, run_date):
    """Deduplication keeps the first record seen, but the surviving rows are
    always emitted in the same sorted order."""
    unique_records = [r for r in sample_paper_records if r.paper_id != "doi_2024_005"]
    forward = build_clean_dataframe(unique_records, run_date)
    backward = build_clean_dataframe(list(reversed(unique_records)), run_date)
    assert forward.equals(backward)


def test_invalid_published_date_yields_sentinel(sample_paper_records, run_date):
    broken = replace(sample_paper_records[0], published="not-a-date")
    df = build_clean_dataframe([broken], run_date)
    assert df.iloc[0]["age_days"] == -1
    assert df.iloc[0]["published"] == ""


def test_input_records_not_mutated(sample_paper_records, run_date):
    before = [record.authors.copy() for record in sample_paper_records]
    build_clean_dataframe(sample_paper_records, run_date)
    after = [record.authors for record in sample_paper_records]
    assert before == after
