"""The Gemini adapter, exercised against a stubbed SDK client (no network)."""

from __future__ import annotations

import types as pytypes

import pytest
from google import genai

from app.graph.schemas import ProductResolutionLLM
from app.providers.base import ProviderError
from app.providers.llm import GeminiLLMProvider


class _StubModels:
    def __init__(self, *, text="", parsed=None, embeddings=None, fail_times=0) -> None:
        self.text = text
        self.parsed = parsed
        self.embeddings = embeddings or []
        self.fail_times = fail_times
        self.calls: list[dict] = []

    async def generate_content(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("transient upstream error")
        return pytypes.SimpleNamespace(text=self.text, parsed=self.parsed)

    async def embed_content(self, *, model, contents):
        self.calls.append({"model": model, "contents": contents})
        return pytypes.SimpleNamespace(
            embeddings=[pytypes.SimpleNamespace(values=vector) for vector in self.embeddings]
        )


def _install(monkeypatch, models: _StubModels):
    client = pytypes.SimpleNamespace(aio=pytypes.SimpleNamespace(models=models))
    monkeypatch.setattr(genai, "Client", lambda **kwargs: client)


def _settings_with_key(settings):
    return settings.model_copy(update={"gemini_api_key": "test-key", "demo_mode": False})


def test_provider_requires_an_api_key(settings):
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiLLMProvider(settings)


async def test_generate_returns_trimmed_text(settings, monkeypatch):
    models = _StubModels(text="  a plain answer  ")
    _install(monkeypatch, models)
    provider = GeminiLLMProvider(_settings_with_key(settings))

    assert await provider.generate("prompt") == "a plain answer"
    assert models.calls[0]["model"] == settings.gemini_model


async def test_structured_generation_requests_a_json_schema(settings, monkeypatch):
    parsed = ProductResolutionLLM(canonical_name="Sony WH-1000XM6", brand="Sony", confidence=0.9)
    models = _StubModels(parsed=parsed)
    _install(monkeypatch, models)
    provider = GeminiLLMProvider(_settings_with_key(settings))

    result = await provider.generate_structured("prompt", ProductResolutionLLM)
    assert result.brand == "Sony"
    config = models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ProductResolutionLLM


async def test_structured_generation_parses_raw_json_when_the_sdk_does_not(settings, monkeypatch):
    models = _StubModels(text='{"canonical_name": "Sony WH-1000XM6", "brand": "Sony"}', parsed=None)
    _install(monkeypatch, models)
    provider = GeminiLLMProvider(_settings_with_key(settings))

    result = await provider.generate_structured("prompt", ProductResolutionLLM)
    assert result.canonical_name == "Sony WH-1000XM6"


async def test_transient_failures_are_retried_then_surface_as_provider_error(
    settings, monkeypatch
):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    models = _StubModels(text="ok", fail_times=1)
    _install(monkeypatch, models)
    provider = GeminiLLMProvider(_settings_with_key(settings))
    assert await provider.generate("prompt") == "ok"

    always_failing = _StubModels(fail_times=99)
    _install(monkeypatch, always_failing)
    provider = GeminiLLMProvider(_settings_with_key(settings))
    with pytest.raises(ProviderError, match="Gemini generate"):
        await provider.generate("prompt")
    assert len(always_failing.calls) == 3


async def test_embeddings_are_unwrapped(settings, monkeypatch):
    models = _StubModels(embeddings=[[0.1, 0.2], [0.3, 0.4]])
    _install(monkeypatch, models)
    provider = GeminiLLMProvider(_settings_with_key(settings))

    assert await provider.embed(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert await provider.embed([]) == []
    assert models.calls[0]["model"] == settings.gemini_embedding_model


async def _no_sleep(_seconds):
    return None
