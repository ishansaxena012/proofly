"""Search providers.

The default *live* implementation needs no API key: it queries DuckDuckGo's
public HTML endpoint and parses the result list. Keyed implementations (Tavily,
SerpApi, Bing) are selected via ``SEARCH_PROVIDER`` + ``SEARCH_API_KEY``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.fixtures import golden, matches_golden_fixture
from app.providers.base import ProviderError, SearchProvider, SearchResult, WebDocument
from app.providers.fetching import HtmlFetcher

log = logging.getLogger(__name__)


class DuckDuckGoSearchProvider(SearchProvider):
    """Keyless public HTML search. This is the live default."""

    name = "duckduckgo"
    ENDPOINT = "https://html.duckduckgo.com/html/"

    def __init__(self, settings: Settings, fetcher: HtmlFetcher | None = None) -> None:
        self._settings = settings
        self._fetcher = fetcher or HtmlFetcher(settings)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        client = await self._fetcher.client()
        try:
            response = await client.post(
                self.ENDPOINT,
                data={"q": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"web search failed for {query!r}: {exc}") from exc

        soup = BeautifulSoup(response.text, "lxml")
        results: list[SearchResult] = []
        for anchor in soup.select("a.result__a"):
            href = anchor.get("href", "")
            url = _unwrap_duckduckgo_url(href)
            if not url.startswith("http"):
                continue
            container = anchor.find_parent(class_="result") or anchor.parent
            snippet_el = container.select_one(".result__snippet") if container else None
            results.append(
                SearchResult(
                    url=url,
                    title=anchor.get_text(" ", strip=True),
                    snippet=snippet_el.get_text(" ", strip=True) if snippet_el else "",
                )
            )
            if len(results) >= limit:
                break
        return results

    async def fetch(self, url: str) -> WebDocument:
        return await self._fetcher.fetch(url)


def _unwrap_duckduckgo_url(href: str) -> str:
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return target[0]
    return href


class TavilySearchProvider(SearchProvider):
    name = "tavily"
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, settings: Settings, fetcher: HtmlFetcher | None = None) -> None:
        if not settings.search_api_key:
            raise ProviderError("SEARCH_API_KEY is required for the Tavily search provider")
        self._settings = settings
        self._fetcher = fetcher or HtmlFetcher(settings)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        client = await self._fetcher.client()
        try:
            response = await client.post(
                self.ENDPOINT,
                json={
                    "api_key": self._settings.search_api_key,
                    "query": query,
                    "max_results": limit,
                    "search_depth": "advanced",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"tavily search failed for {query!r}: {exc}") from exc
        return [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("content", "")[:400],
                published_at=_iso_date(item.get("published_date")),
            )
            for item in payload.get("results", [])
            if item.get("url")
        ][:limit]

    async def fetch(self, url: str) -> WebDocument:
        return await self._fetcher.fetch(url)


class SerpApiSearchProvider(SearchProvider):
    name = "serpapi"
    ENDPOINT = "https://serpapi.com/search.json"

    def __init__(self, settings: Settings, fetcher: HtmlFetcher | None = None) -> None:
        if not settings.search_api_key:
            raise ProviderError("SEARCH_API_KEY is required for the SerpApi search provider")
        self._settings = settings
        self._fetcher = fetcher or HtmlFetcher(settings)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        client = await self._fetcher.client()
        try:
            response = await client.get(
                self.ENDPOINT,
                params={
                    "q": query,
                    "engine": "google",
                    "num": limit,
                    "api_key": self._settings.search_api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"serpapi search failed for {query!r}: {exc}") from exc
        return [
            SearchResult(
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                published_at=_iso_date(item.get("date")),
            )
            for item in payload.get("organic_results", [])
            if item.get("link")
        ][:limit]

    async def fetch(self, url: str) -> WebDocument:
        return await self._fetcher.fetch(url)


class BingSearchProvider(SearchProvider):
    name = "bing"
    ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, settings: Settings, fetcher: HtmlFetcher | None = None) -> None:
        if not settings.search_api_key:
            raise ProviderError("SEARCH_API_KEY is required for the Bing search provider")
        self._settings = settings
        self._fetcher = fetcher or HtmlFetcher(settings)

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        client = await self._fetcher.client()
        try:
            response = await client.get(
                self.ENDPOINT,
                params={"q": query, "count": limit, "responseFilter": "Webpages"},
                headers={"Ocp-Apim-Subscription-Key": self._settings.search_api_key},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"bing search failed for {query!r}: {exc}") from exc
        return [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("name", ""),
                snippet=item.get("snippet", ""),
                published_at=_iso_date(item.get("datePublished")),
            )
            for item in payload.get("webPages", {}).get("value", [])
            if item.get("url")
        ][:limit]

    async def fetch(self, url: str) -> WebDocument:
        return await self._fetcher.fetch(url)


class MockSearchProvider(SearchProvider):
    """Deterministic fixture-backed search. No network, ever."""

    name = "mock"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._documents = {doc.url: doc for doc in golden.WEB_DOCUMENTS}

    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        if not matches_golden_fixture(query):
            # No fixture exists for this product. Returning nothing is the honest
            # answer; inventing sources is not an option.
            return []
        ranked = sorted(
            golden.WEB_SEARCH_RESULTS,
            key=lambda result: (-_overlap(query, f"{result.title} {result.snippet}"), result.url),
        )
        return ranked[:limit]

    async def fetch(self, url: str) -> WebDocument:
        if url == golden.BROKEN_WEB_URL:
            raise ProviderError(
                "fixture source is intentionally unavailable (exercises graceful degradation)"
            )
        document = self._documents.get(url)
        if document is None:
            raise ProviderError(f"no fixture document for {url}")
        return document


def _overlap(query: str, text: str) -> int:
    query_tokens = {token for token in query.lower().split() if len(token) > 2}
    text_tokens = set(text.lower().split())
    return len(query_tokens & text_tokens)


def _iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None
