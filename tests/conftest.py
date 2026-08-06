from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ingestion.crossref import PaperRecord


@pytest.fixture
def sample_paper_records() -> list[PaperRecord]:
    """Generate synthetic PaperRecord list for testing."""
    return [
        PaperRecord(
            paper_id="doi_2024_001",
            title="Machine Learning for Retrieval Augmented Generation",
            summary="This paper explores how machine learning techniques can improve retrieval augmented generation systems.",
            authors=["Alice Smith", "Bob Johnson"],
            categories=["Computer Science", "Machine Learning"],
            primary_category="CS.AI",
            published="2024-01-15",
            updated="2024-01-20",
            abs_url="https://arxiv.org/abs/2024.001",
            pdf_url="https://arxiv.org/pdf/2024.001.pdf",
            comment="",
        ),
        PaperRecord(
            paper_id="doi_2024_002",
            title="Large Language Models in Information Retrieval",
            summary="We present a comprehensive study of LLM applications in information retrieval tasks.",
            authors=["Carol White", "David Lee"],
            categories=["Natural Language Processing", "Information Retrieval"],
            primary_category="CS.CL",
            published="2024-02-01",
            updated="2024-02-05",
            abs_url="https://arxiv.org/abs/2024.002",
            pdf_url="https://arxiv.org/pdf/2024.002.pdf",
            comment="",
        ),
        PaperRecord(
            paper_id="doi_2024_003",
            title="Evaluation Metrics for Question Answering Systems",
            summary="This work proposes novel evaluation metrics for QA systems that better reflect user satisfaction.",
            authors=["Eve Brown"],
            categories=["Evaluation", "Question Answering"],
            primary_category="CS.CL",
            published="2024-03-10",
            updated="2024-03-12",
            abs_url="https://arxiv.org/abs/2024.003",
            pdf_url="https://arxiv.org/pdf/2024.003.pdf",
            comment="",
        ),
        PaperRecord(
            paper_id="doi_2024_004",
            title="Knowledge Graph Construction from Unstructured Text",
            summary="   We describe a pipeline for building knowledge graphs from raw text using NLP techniques.   ",
            authors=["Frank Martinez", "Grace Chen", "Henry Davis"],
            categories=["Knowledge Graphs", "NLP"],
            primary_category="CS.AI",
            published="2024-01-05",
            updated="2024-01-10",
            abs_url="https://arxiv.org/abs/2024.004",
            pdf_url="https://arxiv.org/pdf/2024.004.pdf",
            comment="",
        ),
        PaperRecord(
            paper_id="doi_2024_005",
            title="Machine Learning for Retrieval Augmented Generation",
            summary="Duplicate of paper 001 - should be removed.",
            authors=["Different Author"],
            categories=["Duplicates"],
            primary_category="CS.AI",
            published="2024-01-16",
            updated="2024-01-21",
            abs_url="https://arxiv.org/abs/2024.005",
            pdf_url="https://arxiv.org/pdf/2024.005.pdf",
            comment="",
        ),
        PaperRecord(
            paper_id="doi_2024_006",
            title="",
            summary="Paper with empty title - should be removed.",
            authors=["Ivan Park"],
            categories=["Invalid"],
            primary_category="CS.AI",
            published="2024-04-01",
            updated="2024-04-02",
            abs_url="https://arxiv.org/abs/2024.006",
            pdf_url="https://arxiv.org/pdf/2024.006.pdf",
            comment="",
        ),
        PaperRecord(
            paper_id="doi_2024_007",
            title="Vector Embeddings for NLP",
            summary="",
            authors=["Julia Stone"],
            categories=["Embeddings"],
            primary_category="CS.CL",
            published="2024-04-15",
            updated="2024-04-16",
            abs_url="https://arxiv.org/abs/2024.007",
            pdf_url="https://arxiv.org/pdf/2024.007.pdf",
            comment="",
        ),
    ]


@pytest.fixture
def run_date() -> datetime:
    """Fixed run_date for deterministic age_days calculation."""
    return datetime(2024, 5, 1, tzinfo=UTC)
