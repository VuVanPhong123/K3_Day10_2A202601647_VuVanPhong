from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
import requests

from core.config import load_settings
from ingestion import crossref
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records, parse_crossref_payload


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "crossref_response.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, headers: dict | None = None) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(response=response)


def settings_with_raw_paths(tmp_path: Path):
    settings = load_settings(tmp_path)
    paths = replace(
        settings.paths,
        raw_api_response=tmp_path / "raw" / "crossref_response.json",
        raw_records_json=tmp_path / "raw" / "crossref_records.json",
    )
    return replace(settings, paths=paths, source_query="test query", source_filter="has-abstract:true", max_results=7)


def test_parse_crossref_payload_extracts_all_required_fields_and_cleans_markup() -> None:
    records = parse_crossref_payload(load_fixture())

    assert len(records) == 2
    first = records[0]
    assert first.paper_id == "10.1234/rag.2025.001"
    assert first.title == "Observability for Retrieval-Augmented Generation"
    assert first.summary == (
        "We study data quality & reliable RAG pipelines. Kết quả cải thiện retrieval."
    )
    assert first.authors == ["An Nguyễn", "Minh Tran"]
    assert first.categories == ["Artificial Intelligence", "Information Systems"]
    assert first.primary_category == "Artificial Intelligence"
    assert first.published == "2025-03-14"
    assert first.updated == "2025-04-01"
    assert first.abs_url == "https://doi.org/10.1234/rag.2025.001"
    assert first.pdf_url == "https://example.org/article.pdf"
    assert first.comment == "A reproducible pipeline"


def test_parse_crossref_payload_handles_fallbacks_and_filters_invalid_records() -> None:
    records = parse_crossref_payload(load_fixture())

    second = records[1]
    assert second.authors == ["Crossref Test Consortium"]
    assert second.categories == []
    assert second.primary_category == ""
    assert second.published == "2024-07-01"
    assert second.updated == "2024-08-02"
    assert second.pdf_url == ""
    assert {record.paper_id for record in records}.isdisjoint(
        {"10.1234/missing-title", "10.1234/missing-abstract"}
    )


@pytest.mark.parametrize("payload", [{}, {"message": {}}, {"message": {"items": None}}])
def test_parse_crossref_payload_handles_missing_container_fields(payload: dict) -> None:
    assert parse_crossref_payload(payload) == []


def test_fetch_persists_utf8_response_and_records_and_uses_expected_request(monkeypatch, tmp_path: Path) -> None:
    payload = load_fixture()
    settings = settings_with_raw_paths(tmp_path)
    captured: dict = {}

    def fake_get(url: str, *, params: dict, timeout: int) -> FakeResponse:
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse(payload)

    monkeypatch.setattr(crossref.requests, "get", fake_get)
    records = fetch_source_records(settings)

    assert captured == {
        "url": crossref.CROSSREF_API_URL,
        "params": {"query": "test query", "filter": "has-abstract:true", "rows": 7},
        "timeout": crossref.REQUEST_TIMEOUT_SECONDS,
    }
    assert settings.paths.raw_api_response.read_text(encoding="utf-8").startswith("{\n")
    assert "Kết quả" in settings.paths.raw_api_response.read_text(encoding="utf-8")
    assert "Nguyễn" in settings.paths.raw_records_json.read_text(encoding="utf-8")
    assert load_raw_records(settings.paths.raw_records_json) == records


def test_fetch_retries_retryable_status_with_backoff_then_succeeds(monkeypatch, tmp_path: Path) -> None:
    settings = settings_with_raw_paths(tmp_path)
    responses = [
        FakeResponse({}, 429, {"Retry-After": "0.25"}),
        FakeResponse({}, 503),
        FakeResponse(load_fixture()),
    ]
    sleep_calls: list[float] = []

    monkeypatch.setattr(crossref.requests, "get", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(crossref.time, "sleep", sleep_calls.append)

    assert len(fetch_source_records(settings)) == 2
    assert sleep_calls == [0.25, 2.0]


@pytest.mark.parametrize("status_code", sorted(crossref.RETRYABLE_STATUS_CODES))
def test_fetch_retries_every_required_retryable_status(monkeypatch, tmp_path: Path, status_code: int) -> None:
    settings = settings_with_raw_paths(tmp_path)
    responses = [FakeResponse({}, status_code), FakeResponse(load_fixture())]
    monkeypatch.setattr(crossref.requests, "get", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(crossref.time, "sleep", lambda _: None)

    assert len(fetch_source_records(settings)) == 2
    assert responses == []


def test_fetch_stops_after_maximum_attempts(monkeypatch, tmp_path: Path) -> None:
    settings = settings_with_raw_paths(tmp_path)
    request_count = 0

    def always_unavailable(*args, **kwargs) -> FakeResponse:
        nonlocal request_count
        request_count += 1
        return FakeResponse({}, 504)

    monkeypatch.setattr(crossref.requests, "get", always_unavailable)
    monkeypatch.setattr(crossref.time, "sleep", lambda _: None)

    with pytest.raises(requests.HTTPError):
        fetch_source_records(settings)
    assert request_count == crossref.MAX_REQUEST_ATTEMPTS


def test_fetch_does_not_retry_non_retryable_http_error(monkeypatch, tmp_path: Path) -> None:
    settings = settings_with_raw_paths(tmp_path)
    request_count = 0

    def bad_request(*args, **kwargs) -> FakeResponse:
        nonlocal request_count
        request_count += 1
        return FakeResponse({}, 400)

    monkeypatch.setattr(crossref.requests, "get", bad_request)
    monkeypatch.setattr(crossref.time, "sleep", lambda _: pytest.fail("400 must not be retried"))

    with pytest.raises(requests.HTTPError):
        fetch_source_records(settings)
    assert request_count == 1


def test_load_raw_records_rejects_invalid_snapshot(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text('{"paper_id": "not-a-list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON list"):
        load_raw_records(invalid_path)


def test_load_raw_records_round_trip_preserves_paper_records(tmp_path: Path) -> None:
    path = tmp_path / "records.json"
    expected = PaperRecord(
        paper_id="10.1/example",
        title="Tiêu đề",
        summary="Tóm tắt",
        authors=["Tác Giả"],
        categories=["Data"],
        primary_category="Data",
        published="2026-01-02",
        updated="2026-01-03",
        abs_url="https://doi.org/10.1/example",
        pdf_url="",
        comment="",
    )
    path.write_text(json.dumps([expected.__dict__], ensure_ascii=False), encoding="utf-8")

    assert load_raw_records(path) == [expected]
