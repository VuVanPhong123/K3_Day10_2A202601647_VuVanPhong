from __future__ import annotations

import json
import re

import pytest

from core.utils import first_sentence, read_json
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe


@pytest.fixture
def clean_df(sample_paper_records, run_date):
    return build_clean_dataframe(sample_paper_records, run_date)


@pytest.fixture
def test_set(clean_df, tmp_path):
    return build_test_set(clean_df, tmp_path / "test_set.json")


def test_sample_count_within_expected_range(test_set):
    assert 8 <= len(test_set) <= 12


def test_every_sample_has_required_fields(test_set):
    required = {"id", "question_type", "question", "ground_truth", "ground_truth_doc_ids"}
    for sample in test_set:
        assert required <= set(sample)


def test_covers_all_four_question_types(test_set):
    assert {sample["question_type"] for sample in test_set} == {
        "summary",
        "authors",
        "date",
        "categories",
    }


def test_ids_are_unique(test_set):
    ids = [sample["id"] for sample in test_set]
    assert len(ids) == len(set(ids))


def test_question_quotes_exact_title(test_set, clean_df):
    titles = set(clean_df["title"])
    for sample in test_set:
        match = re.search(r"'([^']+)'", sample["question"])
        assert match is not None, sample["question"]
        assert match.group(1) in titles


def test_ground_truth_doc_ids_exist_in_corpus(test_set, clean_df):
    known = set(clean_df["paper_id"])
    for sample in test_set:
        assert sample["ground_truth_doc_ids"]
        assert set(sample["ground_truth_doc_ids"]) <= known


def test_ground_truth_never_empty(test_set):
    for sample in test_set:
        assert sample["ground_truth"].strip()


def test_ground_truth_matches_source_row(test_set, clean_df):
    by_id = clean_df.set_index("paper_id")
    field_by_type = {
        "authors": "authors_joined",
        "date": "published",
        "categories": "categories_joined",
    }
    for sample in test_set:
        row = by_id.loc[sample["ground_truth_doc_ids"][0]]
        if sample["question_type"] == "summary":
            assert sample["ground_truth"] == first_sentence(row["summary"])
        else:
            assert sample["ground_truth"] == row[field_by_type[sample["question_type"]]]


def test_questions_match_qa_routing_keywords(test_set):
    """`retrieval.qa._extract_answer` dispatches on these lowercase keywords."""
    expected = {
        "authors": "who authored",
        "date": "when was",
        "categories": "what categories",
    }
    for sample in test_set:
        lowered = sample["question"].lower()
        if sample["question_type"] == "summary":
            assert "who authored" not in lowered
            assert "when was" not in lowered
            assert "what categories" not in lowered
        else:
            assert expected[sample["question_type"]] in lowered


def test_writes_json_file(clean_df, tmp_path):
    output = tmp_path / "nested" / "test_set.json"
    returned = build_test_set(clean_df, output)
    assert output.exists()
    assert read_json(output) == returned


def test_deterministic_across_runs(clean_df, tmp_path):
    first = build_test_set(clean_df, tmp_path / "first.json")
    second = build_test_set(clean_df, tmp_path / "second.json")
    assert first == second
    assert json.dumps(first) == json.dumps(second)


def test_rejects_corpus_below_minimum(clean_df, tmp_path):
    with pytest.raises(ValueError):
        build_test_set(clean_df.head(2), tmp_path / "too_small.json")
