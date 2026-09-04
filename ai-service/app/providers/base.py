"""Provider interfaces.

Nothing downstream of this module may know which concrete implementation is
active. Every provider has a deterministic mock counterpart that is selected when
``DEMO_MODE=true`` or when the relevant credential is missing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel, Field


class ProviderError(RuntimeError):
    """Raised by a provider when a channel cannot be served.

    The graph catches this per-channel: a failing channel degrades the run and is
    disclosed in the report caveats, it never kills the job.
    """


# ───────────────────────────── result payloads ─────────────────────────────


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str = ""
    published_at: date | None = None


class WebDocument(BaseModel):
    url: str
    title: str
    text: str
    published_at: date | None = None


class RedditComment(BaseModel):
    id: str
    author: str = ""
    body: str
    score: int = 0


class RedditPost(BaseModel):
    id: str
    url: str
    permalink: str
    subreddit: str
    title: str
    selftext: str = ""
    score: int = 0
    num_comments: int = 0
    created_at: date | None = None
    comments: list[RedditComment] = Field(default_factory=list)


class YouTubeVideo(BaseModel):
    video_id: str
    url: str
    title: str
    channel_title: str = ""
    description: str = ""
    published_at: date | None = None
    transcript: str = ""


# ───────────────────────────── interfaces ──────────────────────────────────


class LLMProvider(ABC):
    """Only implementation allowed to touch a real LLM SDK."""

    name: str = "abstract"

    @abstractmethod
    async def generate(self, prompt: str, *, task: str = "", context: dict | None = None) -> str:
        """Free-form text generation."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        task: str = "",
        context: dict | None = None,
    ) -> BaseModel:
        """Schema-constrained generation. Returns an instance of ``schema``.

        ``task``/``context`` are advisory hints: the live provider folds them into
        the prompt-independent request only for logging, while the deterministic
        mock uses them to produce grounded fixture-derived output.
        """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class SearchProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[SearchResult]:
        ...

    async def search_many(
        self, queries: list[str], *, limit_per_query: int = 10
    ) -> list[SearchResult]:
        seen: set[str] = set()
        merged: list[SearchResult] = []
        for query in queries:
            for result in await self.search(query, limit=limit_per_query):
                if result.url in seen:
                    continue
                seen.add(result.url)
                merged.append(result)
        return merged

    @abstractmethod
    async def fetch(self, url: str) -> WebDocument:
        """Fetch and extract readable text for a result URL."""


class RedditProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def search(self, query: str, *, limit: int = 10) -> list[RedditPost]:
        ...

    async def search_many(self, queries: list[str], *, limit_per_query: int = 10) -> list[RedditPost]:
        seen: set[str] = set()
        merged: list[RedditPost] = []
        for query in queries:
            for post in await self.search(query, limit=limit_per_query):
                if post.id in seen:
                    continue
                seen.add(post.id)
                merged.append(post)
        return merged

    @abstractmethod
    async def fetch_comments(self, post: RedditPost, *, limit: int = 20) -> list[RedditComment]:
        ...


class YouTubeProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def search(self, query: str, *, limit: int = 5) -> list[YouTubeVideo]:
        ...

    async def search_many(self, queries: list[str], *, limit_per_query: int = 5) -> list[YouTubeVideo]:
        seen: set[str] = set()
        merged: list[YouTubeVideo] = []
        for query in queries:
            for video in await self.search(query, limit=limit_per_query):
                if video.video_id in seen:
                    continue
                seen.add(video.video_id)
                merged.append(video)
        return merged

    @abstractmethod
    async def fetch_transcript(self, video: YouTubeVideo) -> str:
        ...
