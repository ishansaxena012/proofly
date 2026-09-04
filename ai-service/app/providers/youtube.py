"""YouTube providers.

Live search uses YouTube Data API v3 (``YOUTUBE_API_KEY``). Transcripts are
retrieved with ``youtube-transcript-api``; when a video has no transcript the
provider returns an empty string and the pipeline falls back to the video
description, which is disclosed rather than filled in with guesses.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx

from app.config import Settings
from app.fixtures import golden, matches_golden_fixture
from app.providers.base import ProviderError, YouTubeProvider, YouTubeVideo
from app.providers.fetching import HtmlFetcher

log = logging.getLogger(__name__)


class DataApiYouTubeProvider(YouTubeProvider):
    name = "youtube-data-api-v3"
    ENDPOINT = "https://www.googleapis.com/youtube/v3/search"

    def __init__(self, settings: Settings, fetcher: HtmlFetcher | None = None) -> None:
        if not settings.youtube_api_key:
            raise ProviderError("YOUTUBE_API_KEY is required for DataApiYouTubeProvider")
        self._settings = settings
        self._fetcher = fetcher or HtmlFetcher(settings)

    async def search(self, query: str, *, limit: int = 5) -> list[YouTubeVideo]:
        client = await self._fetcher.client()
        try:
            response = await client.get(
                self.ENDPOINT,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": limit,
                    "relevanceLanguage": "en",
                    "key": self._settings.youtube_api_key,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"youtube search failed for {query!r}: {exc}") from exc

        videos: list[YouTubeVideo] = []
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            videos.append(
                YouTubeVideo(
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=snippet.get("title", ""),
                    channel_title=snippet.get("channelTitle", ""),
                    description=snippet.get("description", ""),
                    published_at=_iso_date(snippet.get("publishedAt")),
                )
            )
            if len(videos) >= limit:
                break
        return videos

    async def fetch_transcript(self, video: YouTubeVideo) -> str:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - only without the library
            log.warning("youtube-transcript-api unavailable: %s", exc)
            return ""

        def _fetch() -> str:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video.video_id, languages=["en", "en-US", "en-GB"])
            return "\n".join(snippet.text for snippet in fetched if snippet.text.strip())

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:  # noqa: BLE001 - library raises many subclasses
            log.info("no transcript for %s: %s", video.video_id, exc)
            return ""


class MockYouTubeProvider(YouTubeProvider):
    """Deterministic fixture-backed YouTube provider. No network, ever."""

    name = "mock"

    def __init__(self, settings: Settings | None = None, *, fixtures_enabled: bool = True) -> None:
        self._settings = settings
        # Outside demo mode the mock must never emit fixture material into a live
        # report; it reports the channel as unavailable instead.
        self._fixtures_enabled = fixtures_enabled

    async def search(self, query: str, *, limit: int = 5) -> list[YouTubeVideo]:
        if not self._fixtures_enabled:
            raise ProviderError(
                "YouTube is unavailable: no YOUTUBE_API_KEY, and fixture data may not be used "
                "outside demo mode."
            )
        if not matches_golden_fixture(query):
            return []
        ranked = sorted(
            golden.YOUTUBE_VIDEOS,
            key=lambda video: (-_overlap(query, video.title), video.video_id),
        )
        return ranked[:limit]

    async def fetch_transcript(self, video: YouTubeVideo) -> str:
        if not self._fixtures_enabled:
            return ""
        for fixture in golden.YOUTUBE_VIDEOS:
            if fixture.video_id == video.video_id:
                return fixture.transcript
        return ""


def _overlap(query: str, text: str) -> int:
    query_tokens = {token for token in query.lower().split() if len(token) > 2}
    return len(query_tokens & set(text.lower().split()))


def _iso_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None
