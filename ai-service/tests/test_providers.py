"""Provider boundary: mock determinism, live parsing, and selection rules."""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.fixtures import golden
from app.graph.schemas import EvidenceExtractionResult, ProductResolutionLLM
from app.providers.base import ProviderError
from app.providers.factory import build_providers
from app.providers.fetching import HtmlFetcher, extract_readable
from app.providers.llm import MockLLMProvider, deterministic_embedding
from app.providers.reddit import MockRedditProvider
from app.providers.search import DuckDuckGoSearchProvider, MockSearchProvider
from app.providers.youtube import MockYouTubeProvider

# ── selection ──────────────────────────────────────────────────────────────


def test_demo_mode_selects_every_mock(settings):
    bundle = build_providers(settings, demo_mode=True)
    assert bundle.demo_mode is True
    assert {bundle.llm.name, bundle.search.name, bundle.reddit.name, bundle.youtube.name} == {
        "mock"
    }
    assert any("Demo mode" in note for note in bundle.notes)


def test_live_mode_without_credentials_uses_keyless_providers(settings):
    live = settings.model_copy(update={"demo_mode": False, "search_provider": "auto"})
    bundle = build_providers(live, demo_mode=False)
    assert bundle.search.name == "duckduckgo"
    assert bundle.reddit.name == "reddit-public-json"
    assert bundle.llm.name == "mock"
    assert any("GEMINI_API_KEY" in note for note in bundle.notes)
    assert any("YOUTUBE_API_KEY" in note for note in bundle.notes)


async def test_fixture_data_never_leaks_into_a_live_run(settings):
    """A missing YouTube key must not splice demo fixtures into a live report."""

    live = settings.model_copy(update={"demo_mode": False})
    bundle = build_providers(live, demo_mode=False)
    with pytest.raises(ProviderError):
        await bundle.youtube.search("Sony WH-1000XM6")
    await bundle.aclose()


# ── mock determinism ───────────────────────────────────────────────────────


async def test_mock_search_is_deterministic_and_fixture_bound(settings):
    provider = MockSearchProvider(settings)
    first = await provider.search("Sony WH-1000XM6 review", limit=10)
    second = await provider.search("Sony WH-1000XM6 review", limit=10)
    assert [r.url for r in first] == [r.url for r in second]
    assert all(url.startswith("https://fixtures.proofly.invalid") for url in [r.url for r in first])


async def test_mock_providers_return_nothing_for_products_without_a_fixture(settings):
    assert await MockSearchProvider(settings).search("Bose QuietComfort Ultra") == []
    assert await MockRedditProvider(settings).search("Dell XPS 13") == []
    assert await MockYouTubeProvider(settings).search("Pixel 9 Pro") == []


async def test_mock_search_reports_the_intentionally_broken_fixture(settings):
    provider = MockSearchProvider(settings)
    with pytest.raises(ProviderError):
        await provider.fetch(golden.BROKEN_WEB_URL)


async def test_mock_llm_structured_output_is_deterministic():
    llm = MockLLMProvider()
    context = {"query": "Sony WH-1000XM6"}
    first = await llm.generate_structured("", ProductResolutionLLM, task="product_resolution", context=context)
    second = await llm.generate_structured("", ProductResolutionLLM, task="product_resolution", context=context)
    assert first == second
    assert first.brand == "Sony"


async def test_mock_llm_falls_back_to_a_valid_instance_for_unknown_tasks():
    llm = MockLLMProvider()
    result = await llm.generate_structured("prompt", EvidenceExtractionResult, task="unknown-task")
    assert isinstance(result, EvidenceExtractionResult)
    assert result.items == []


async def test_mock_embeddings_are_stable_and_normalised():
    llm = MockLLMProvider()
    vectors = await llm.embed(["battery life", "battery life", "microphone in wind"])
    assert vectors[0] == vectors[1]
    assert vectors[0] != vectors[2]
    assert len(vectors[0]) == 768
    assert abs(sum(value * value for value in vectors[0]) - 1.0) < 1e-6


def test_deterministic_embedding_handles_empty_text():
    assert deterministic_embedding("") == [0.0] * 768


# ── live parsing (offline, via MockTransport) ──────────────────────────────

DDG_HTML = """
<html><body>
  <div class="result">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Freview&amp;rut=x">
      Example review
    </a>
    <div class="result__snippet">A review of the thing.</div>
  </div>
  <div class="result">
    <a class="result__a" href="https://direct.example.org/page">Direct result</a>
    <div class="result__snippet">Another snippet.</div>
  </div>
</body></html>
"""

ARTICLE_HTML = """
<html><head><title>Some Review</title>
<meta property="article:published_time" content="2025-06-02T10:00:00Z"></head>
<body>
  <nav>menu we do not want</nav>
  <article>
    <h1>Some Review</h1>
    <p>The battery lasted twenty eight hours in our continuous playback test.</p>
    <p>short</p>
    <p>Noise cancellation measured thirty two decibels of broadband attenuation.</p>
  </article>
  <footer>footer we do not want</footer>
</body></html>
"""


async def test_duckduckgo_results_are_parsed_and_unwrapped(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "html.duckduckgo.com"
        return httpx.Response(200, text=DDG_HTML)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DuckDuckGoSearchProvider(settings, HtmlFetcher(settings, client=client))
    results = await provider.search("sony wh-1000xm6 review", limit=10)

    assert [r.url for r in results] == [
        "https://example.com/review",
        "https://direct.example.org/page",
    ]
    assert results[0].snippet == "A review of the thing."


def test_readable_extraction_drops_boilerplate():
    document = extract_readable(ARTICLE_HTML, "https://example.com/x")
    assert document.title == "Some Review"
    assert "menu we do not want" not in document.text
    assert "footer we do not want" not in document.text
    assert "twenty eight hours" in document.text
    assert str(document.published_at) == "2025-06-02"


async def test_fetcher_reports_an_unfetchable_page_as_a_provider_error(settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(500)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HtmlFetcher(settings, client=client)
    with pytest.raises(ProviderError):
        await fetcher.fetch("https://example.com/broken")


async def test_fetcher_honours_robots_txt(settings: Settings):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text=ARTICLE_HTML)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HtmlFetcher(settings, client=client)
    with pytest.raises(ProviderError, match="robots.txt"):
        await fetcher.fetch("https://example.com/private/page")
    allowed = await fetcher.fetch("https://example.com/public/page")
    assert allowed.title == "Some Review"
