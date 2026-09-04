"""Provider selection.

Rules (docs/ARCHITECTURE.md §5, docs/ENGINEERING_RULES.md "Provider abstractions"):

* ``DEMO_MODE=true`` → every provider is the deterministic mock backed by
  ``app/fixtures``.
* Otherwise each provider independently picks its live implementation, falling
  back to the mock when its credential is missing.

One safety refinement on top of that rule: a mock provider only emits fixture
data when demo mode is actually on. In a *live* run whose credential happens to
be missing, the mock reports the channel as unavailable instead of quietly
splicing demo fixtures into a real report — that would be fabrication, which
docs/ENGINEERING_RULES.md rule 2 forbids. The channel degrades and the report discloses it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.config import Settings
from app.providers.base import (
    LLMProvider,
    ProviderError,
    RedditProvider,
    SearchProvider,
    YouTubeProvider,
)
from app.providers.fetching import HtmlFetcher
from app.providers.llm import GeminiLLMProvider, MockLLMProvider
from app.providers.reddit import MockRedditProvider, PublicJsonRedditProvider
from app.providers.search import (
    BingSearchProvider,
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SerpApiSearchProvider,
    TavilySearchProvider,
)
from app.providers.youtube import DataApiYouTubeProvider, MockYouTubeProvider

log = logging.getLogger(__name__)


@dataclass
class ProviderBundle:
    llm: LLMProvider
    search: SearchProvider
    reddit: RedditProvider
    youtube: YouTubeProvider
    demo_mode: bool
    notes: list[str] = field(default_factory=list)
    fetcher: HtmlFetcher | None = None

    async def aclose(self) -> None:
        if self.fetcher is not None:
            await self.fetcher.aclose()


def build_providers(settings: Settings, *, demo_mode: bool | None = None) -> ProviderBundle:
    demo = settings.demo_mode if demo_mode is None else demo_mode
    notes: list[str] = []
    fetcher: HtmlFetcher | None = None

    if demo:
        notes.append(
            "Demo mode: all providers are deterministic local fixtures, not live research."
        )
        return ProviderBundle(
            llm=MockLLMProvider(settings),
            search=MockSearchProvider(settings),
            reddit=MockRedditProvider(settings),
            youtube=MockYouTubeProvider(settings),
            demo_mode=True,
            notes=notes,
        )

    fetcher = HtmlFetcher(settings)

    # ── LLM ────────────────────────────────────────────────────────────────
    llm: LLMProvider
    if settings.gemini_available:
        try:
            llm = GeminiLLMProvider(settings)
        except ProviderError as exc:
            log.warning("falling back to mock LLM: %s", exc)
            llm = MockLLMProvider(settings)
            notes.append(f"Gemini unavailable ({exc}); deterministic rule-based analysis was used.")
    else:
        llm = MockLLMProvider(settings)
        notes.append(
            "No GEMINI_API_KEY configured; analysis used Proofly's deterministic rule-based "
            "engine instead of a language model."
        )

    # ── Search ─────────────────────────────────────────────────────────────
    search = _build_search(settings, fetcher, notes)

    # ── Reddit (public JSON endpoint needs no credentials) ─────────────────
    reddit: RedditProvider = PublicJsonRedditProvider(settings, fetcher)

    # ── YouTube ────────────────────────────────────────────────────────────
    youtube: YouTubeProvider
    if settings.youtube_available:
        youtube = DataApiYouTubeProvider(settings, fetcher)
    else:
        youtube = MockYouTubeProvider(settings, fixtures_enabled=False)
        notes.append(
            "No YOUTUBE_API_KEY configured; the YouTube channel was unavailable for this run."
        )

    return ProviderBundle(
        llm=llm,
        search=search,
        reddit=reddit,
        youtube=youtube,
        demo_mode=False,
        notes=notes,
        fetcher=fetcher,
    )


def _build_search(settings: Settings, fetcher: HtmlFetcher, notes: list[str]) -> SearchProvider:
    choice = (settings.search_provider or "auto").strip().lower()
    keyed = {
        "tavily": TavilySearchProvider,
        "serpapi": SerpApiSearchProvider,
        "bing": BingSearchProvider,
    }
    if choice == "mock":
        notes.append("SEARCH_PROVIDER=mock: web search used deterministic fixtures.")
        return MockSearchProvider(settings)
    if choice in keyed:
        try:
            return keyed[choice](settings, fetcher)
        except ProviderError as exc:
            notes.append(
                f"Configured search provider '{choice}' is unusable ({exc}); "
                f"fell back to keyless public web search."
            )
    return DuckDuckGoSearchProvider(settings, fetcher)
