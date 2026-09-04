"""Shared HTTP fetching + readable-text extraction for the live providers."""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.robotparser
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.providers.base import ProviderError, WebDocument

log = logging.getLogger(__name__)

_BOILERPLATE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "form", "noscript")
_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def extract_readable(html: str, url: str) -> WebDocument:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()

    published_at = _extract_published_date(soup)

    for tag in soup(list(_BOILERPLATE_TAGS)):
        tag.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    chunks: list[str] = []
    for element in container.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        text = element.get_text(" ", strip=True)
        if len(text.split()) >= 4:
            chunks.append(text)
    if not chunks:
        chunks = [container.get_text(" ", strip=True)]

    body = "\n\n".join(chunks)
    body = _WHITESPACE_RE.sub(" ", body)
    body = _BLANKLINES_RE.sub("\n\n", body).strip()

    return WebDocument(url=url, title=title or url, text=body, published_at=published_at)


def _extract_published_date(soup: BeautifulSoup) -> date | None:
    candidates: list[str] = []
    for attrs in (
        {"property": "article:published_time"},
        {"name": "article:published_time"},
        {"name": "date"},
        {"itemprop": "datePublished"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            candidates.append(tag["content"])
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        candidates.append(time_tag["datetime"])
    for raw in candidates:
        parsed = _parse_date(raw)
        if parsed:
            return parsed
    return None


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for pattern in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.replace("Z", "+0000"), pattern).date()
        except ValueError:
            continue
    return None


class HtmlFetcher:
    """Polite HTTP fetcher: identifies itself, honours robots.txt and times out."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._robots_lock = asyncio.Lock()

    async def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._settings.http_timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": self._settings.http_user_agent},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        async with self._robots_lock:
            if origin not in self._robots:
                parser: urllib.robotparser.RobotFileParser | None = None
                try:
                    client = await self.client()
                    response = await client.get(urljoin(origin, "/robots.txt"))
                    if response.status_code == 200:
                        parser = urllib.robotparser.RobotFileParser()
                        parser.parse(response.text.splitlines())
                except Exception as exc:  # noqa: BLE001 - robots is best-effort
                    log.debug("robots.txt unavailable for %s: %s", origin, exc)
                self._robots[origin] = parser
            parser = self._robots[origin]
        if parser is None:
            return True
        return parser.can_fetch(self._settings.http_user_agent, url)

    async def get_text(self, url: str) -> str:
        client = await self.client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    async def fetch(self, url: str) -> WebDocument:
        if not await self._allowed(url):
            raise ProviderError(f"robots.txt disallows fetching {url}")
        try:
            html = await self.get_text(url)
        except httpx.HTTPError as exc:
            raise ProviderError(f"failed to fetch {url}: {exc}") from exc
        document = extract_readable(html, url)
        if not document.text.strip():
            raise ProviderError(f"no readable content extracted from {url}")
        return document
