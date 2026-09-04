"""Reddit providers.

The live implementation uses Reddit's public JSON endpoints, which need no OAuth
credentials — only a descriptive User-Agent (``REDDIT_USER_AGENT``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.fixtures import golden, matches_golden_fixture
from app.providers.base import ProviderError, RedditComment, RedditPost, RedditProvider
from app.providers.fetching import HtmlFetcher

log = logging.getLogger(__name__)


class PublicJsonRedditProvider(RedditProvider):
    """Reddit public JSON search (`/search.json`) + per-post comment JSON."""

    name = "reddit-public-json"
    BASE = "https://www.reddit.com"

    def __init__(self, settings: Settings, fetcher: HtmlFetcher | None = None) -> None:
        self._settings = settings
        self._fetcher = fetcher or HtmlFetcher(settings)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._settings.reddit_user_agent or self._settings.http_user_agent,
            "Accept": "application/json",
        }

    async def search(self, query: str, *, limit: int = 10) -> list[RedditPost]:
        client = await self._fetcher.client()
        try:
            response = await client.get(
                f"{self.BASE}/search.json",
                params={"q": query, "limit": limit, "sort": "relevance", "t": "year", "raw_json": 1},
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"reddit search failed for {query!r}: {exc}") from exc

        posts: list[RedditPost] = []
        for child in payload.get("data", {}).get("children", []):
            data = child.get("data", {})
            permalink = data.get("permalink", "")
            if not permalink:
                continue
            posts.append(
                RedditPost(
                    id=data.get("id", permalink),
                    url=f"{self.BASE}{permalink}",
                    permalink=permalink,
                    subreddit=data.get("subreddit", ""),
                    title=data.get("title", ""),
                    selftext=data.get("selftext", "") or "",
                    score=int(data.get("score", 0) or 0),
                    num_comments=int(data.get("num_comments", 0) or 0),
                    created_at=_epoch_to_date(data.get("created_utc")),
                )
            )
            if len(posts) >= limit:
                break
        return posts

    async def fetch_comments(self, post: RedditPost, *, limit: int = 20) -> list[RedditComment]:
        client = await self._fetcher.client()
        try:
            response = await client.get(
                f"{self.BASE}{post.permalink}.json",
                params={"limit": limit, "sort": "top", "raw_json": 1},
                headers=self._headers(),
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"reddit comment fetch failed for {post.url}: {exc}") from exc

        comments: list[RedditComment] = []
        if isinstance(payload, list) and len(payload) > 1:
            for child in payload[1].get("data", {}).get("children", []):
                data = child.get("data", {})
                body = (data.get("body") or "").strip()
                if not body or body in ("[deleted]", "[removed]"):
                    continue
                comments.append(
                    RedditComment(
                        id=data.get("id", ""),
                        author=data.get("author", ""),
                        body=body,
                        score=int(data.get("score", 0) or 0),
                    )
                )
                if len(comments) >= limit:
                    break
        return comments


class MockRedditProvider(RedditProvider):
    """Deterministic fixture-backed Reddit provider. No network, ever."""

    name = "mock"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    async def search(self, query: str, *, limit: int = 10) -> list[RedditPost]:
        if not matches_golden_fixture(query):
            return []
        ranked = sorted(
            golden.REDDIT_POSTS,
            key=lambda post: (-_overlap(query, f"{post.title} {post.selftext}"), post.id),
        )
        return ranked[:limit]

    async def fetch_comments(self, post: RedditPost, *, limit: int = 20) -> list[RedditComment]:
        for fixture_post in golden.REDDIT_POSTS:
            if fixture_post.id == post.id:
                return list(fixture_post.comments)[:limit]
        return []


def _overlap(query: str, text: str) -> int:
    query_tokens = {token for token in query.lower().split() if len(token) > 2}
    return len(query_tokens & set(text.lower().split()))


def _epoch_to_date(value: object):
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).date()  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
