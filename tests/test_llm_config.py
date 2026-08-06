from __future__ import annotations

from dataclasses import replace

import pytest

from core.config import load_settings, require_llm_credentials
import retrieval.llm as llm_module


def _settings(tmp_path, monkeypatch):
    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "CUSTOM_LLM_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    return load_settings(project_dir=tmp_path)


def test_default_provider_and_model_are_gemini(monkeypatch, tmp_path):
    settings = _settings(tmp_path, monkeypatch)

    assert settings.llm_provider == "gemini"
    assert settings.model_name == "gemini-3.5-flash-lite"


def test_credentials_are_required_only_for_selected_provider(monkeypatch, tmp_path):
    settings = _settings(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        require_llm_credentials(settings)

    openai_settings = replace(
        settings,
        llm_provider="openai",
        google_api_key=None,
        openai_api_key="openai-test-key",
    )
    require_llm_credentials(openai_settings)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        require_llm_credentials(replace(openai_settings, openai_api_key=None))


def test_gemini_3_does_not_receive_temperature(monkeypatch, tmp_path):
    settings = replace(
        _settings(tmp_path, monkeypatch),
        google_api_key="google-test-key",
    )
    captured = {}

    class DummyGemini:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_module, "ChatGoogleGenerativeAI", DummyGemini)
    llm_module.build_llm(settings, temperature=0.8)

    assert captured["model"] == "gemini-3.5-flash-lite"
    assert captured["google_api_key"]
    assert "temperature" not in captured


def test_openai_uses_selected_model_and_key_without_api_call(monkeypatch, tmp_path):
    settings = replace(
        _settings(tmp_path, monkeypatch),
        llm_provider="openai",
        model_name="gpt-test-model",
        openai_api_key="openai-test-key",
    )
    captured = {}

    class DummyOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_module, "ChatOpenAI", DummyOpenAI)
    llm_module.build_llm(settings, temperature=0.2)

    assert captured["model"] == "gpt-test-model"
    assert captured["api_key"]
