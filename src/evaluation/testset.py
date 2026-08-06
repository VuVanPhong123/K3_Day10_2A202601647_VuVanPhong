from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS = 3
PAPERS_PER_TEST_SET = 3

# Each template is phrased so that `retrieval.qa._extract_answer` routes it to the
# matching metadata field, and every question quotes the exact title so that
# `qa.answer_question` can resolve the document through `index.lookup`.
QUESTION_TEMPLATES: list[tuple[str, str, str]] = [
    ("summary", "What is the paper '{title}' about?", "summary"),
    ("authors", "Who authored the paper '{title}'?", "authors_joined"),
    ("date", "When was the paper '{title}' published?", "published"),
    ("categories", "What categories are assigned to the paper '{title}'?", "categories_joined"),
]


def _ground_truth(question_type: str, row: pd.Series) -> str:
    """Mirror how `qa._extract_answer` derives an answer from document metadata."""
    if question_type == "summary":
        return first_sentence(str(row["summary"]))
    field = {
        "authors": "authors_joined",
        "date": "published",
        "categories": "categories_joined",
    }[question_type]
    return str(row[field])


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a deterministic evaluation set from the cleaned dataframe.

    Produces four question types (summary, authors, date, categories) for each
    selected paper, so a run over three papers yields twelve samples. Selection
    follows the deterministic row order of `df`, which means the same input
    always produces the same test set.
    """
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(
            f"Need at least {MIN_DOCUMENTS} cleaned documents to build a test set, got {len(df)}."
        )

    selected = df.head(PAPERS_PER_TEST_SET)

    test_set: list[dict[str, Any]] = []
    for position, (_, row) in enumerate(selected.iterrows(), start=1):
        title = str(row["title"])
        paper_id = str(row["paper_id"])
        for question_type, template, _field in QUESTION_TEMPLATES:
            test_set.append(
                {
                    "id": f"q{position:02d}_{question_type}",
                    "question_type": question_type,
                    "question": template.format(title=title),
                    "ground_truth": _ground_truth(question_type, row),
                    "ground_truth_doc_ids": [paper_id],
                }
            )

    write_json(output_path, test_set)
    return test_set
