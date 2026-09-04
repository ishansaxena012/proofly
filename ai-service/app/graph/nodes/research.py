"""Nodes 3-5 — the web / Reddit / YouTube research channels.

The three channels are independent branches of the graph. A channel that fails —
provider outage, missing credential, rate limit — records the failure, degrades,
and lets the run continue on the remaining channels; the limitation is carried
through to the report's caveats. A single source that fails to fetch is recorded
as a ``FAILED`` source and skipped.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from app.graph.context import JobContext
from app.graph.state import ResearchState
from app.models.domain import Document, Passage, Source
from app.models.enums import Channel, EventType, SourceStatus, SourceType
from app.providers.base import ProviderError
from app.services.chunking import build_document, split_passages
from app.services.heuristics import MEASUREMENT_RE, count_markers, estimate_tokens

log = logging.getLogger(__name__)

EMBED_BATCH = 32

_USER_FEEDBACK_MARKERS = ("owner", "owners", "feedback", "roundup", "we collected", "customers")


def publisher_key(url: str) -> str:
    """The entity that published a page.

    For real URLs that is the host. Fixture URLs all share one reserved host, so
    the publisher slug is the first path segment after the channel segment.
    """

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.endswith(".invalid") or host.endswith(".local"):
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) >= 2:
            return segments[1].lower()
    return host


def classify_web_source(
    url: str, title: str, text: str, brand: str | None
) -> tuple[SourceType, float, bool]:
    publisher = publisher_key(url)
    haystack = f"{title} {url}".lower()
    brand_token = (brand or "").strip().lower()

    if brand_token and brand_token in publisher:
        # Manufacturer-published material: useful for specifications, never an
        # independent opinion about its own product.
        return SourceType.OFFICIAL_DOC, 0.55, False

    if count_markers(f" {title.lower()} {text[:600].lower()} ", _USER_FEEDBACK_MARKERS) >= 2:
        return SourceType.USER_EXPERIENCE, 0.55, True

    if "review" in haystack and len(text.split()) >= 150:
        authority = 0.75
        if MEASUREMENT_RE.search(text.lower()):
            authority = 0.85
        return SourceType.PROFESSIONAL_REVIEW, authority, True

    return SourceType.GENERIC, 0.45, False


async def _embed_passages(ctx: JobContext, passages: list[Passage]) -> None:
    for start in range(0, len(passages), EMBED_BATCH):
        batch = passages[start : start + EMBED_BATCH]
        try:
            vectors = await ctx.llm.embed([passage.text for passage in batch])
        except Exception as exc:  # noqa: BLE001 - embeddings are an optimisation
            log.warning("embedding batch failed: %s", exc)
            return
        for passage, vector in zip(batch, vectors, strict=False):
            passage.embedding = vector


def _make_records(
    ctx: JobContext,
    *,
    channel: Channel,
    url: str,
    title: str,
    text: str,
    source_type: SourceType,
    authority: float,
    first_hand: bool,
    published_at=None,
) -> tuple[Source, Document, list[Passage]] | None:
    tokens = estimate_tokens(text)
    if not ctx.budget.take_document_tokens(tokens):
        return None
    source = Source(
        channel=channel,
        url=url,
        title=title,
        source_type=source_type,
        authority_score=authority,
        first_hand=first_hand,
        status=SourceStatus.FETCHED,
        published_at=published_at,
        raw_text=text,
        is_demo_fixture=ctx.demo_mode,
    )
    document = build_document(source.id, text)
    passages = split_passages(document)
    return source, document, passages


def _failed_source(channel: Channel, url: str, title: str, reason: str) -> Source:
    return Source(
        channel=channel,
        url=url,
        title=title,
        source_type=SourceType.GENERIC,
        authority_score=0.0,
        first_hand=False,
        status=SourceStatus.FAILED,
        failure_reason=reason[:500],
    )


async def _finalise_channel(
    ctx: JobContext,
    channel: Channel,
    event_type: EventType,
    sources: list[Source],
    documents: list[Document],
    passages: list[Passage],
    limitations: list[str],
    error: str | None,
) -> dict:
    await ctx.backend.post_sources(ctx.job_id, sources)
    fetched = [source for source in sources if source.status == SourceStatus.FETCHED]
    failed = [source for source in sources if source.status == SourceStatus.FAILED]
    message = (
        f"{channel.value} research failed: {error}"
        if error
        else f"{channel.value} research collected {len(fetched)} source(s)."
    )
    await ctx.backend.post_event(
        ctx.job_id,
        event_type,
        message,
        {
            "channel": channel.value,
            "status": "FAILED" if error else "OK",
            "fetchedSources": len(fetched),
            "failedSources": len(failed),
            "passages": len(passages),
            "error": error,
        },
    )
    if failed:
        limitations.append(
            f"{len(failed)} {channel.value.lower()} source(s) could not be retrieved and were "
            f"excluded from the analysis."
        )
    return {
        "sources": sources,
        "documents": documents,
        "passages": passages,
        "limitations": limitations,
        "channel_outcomes": {
            channel.value: {
                "status": "FAILED" if error else "OK",
                "sources": len(fetched),
                "error": error or "",
            }
        },
    }


# ───────────────────────────── web ─────────────────────────────────────────


async def web_research_node(ctx: JobContext, state: ResearchState) -> dict:
    plan = state["plan"]
    product = state["product"]
    sources: list[Source] = []
    documents: list[Document] = []
    passages: list[Passage] = []
    limitations: list[str] = []
    error: str | None = None

    try:
        ctx.budget.check_deadline()
        queries = list(plan.web_queries)
        results = await ctx.providers.search.search_many(queries, limit_per_query=10)
        if not results:
            limitations.append("Web search returned no results for this product.")
        for result in results:
            ctx.budget.check_deadline()
            if ctx.budget.sources_exhausted():
                break
            if not ctx.budget.take_page(result.url):
                continue
            try:
                document = await ctx.providers.search.fetch(result.url)
            except Exception as exc:  # noqa: BLE001 - one bad page must not stop the channel
                log.info("web fetch failed for %s: %s", result.url, exc)
                sources.append(_failed_source(Channel.WEB, result.url, result.title, str(exc)))
                continue
            source_type, authority, first_hand = classify_web_source(
                document.url, document.title or result.title, document.text, product.brand
            )
            record = _make_records(
                ctx,
                channel=Channel.WEB,
                url=document.url,
                title=document.title or result.title,
                text=document.text,
                source_type=source_type,
                authority=authority,
                first_hand=first_hand,
                published_at=document.published_at or result.published_at,
            )
            if record is None:
                break
            ctx.budget.take_source()
            source, doc, chunks = record
            sources.append(source)
            documents.append(doc)
            passages.extend(chunks)
    except ProviderError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001 - a channel never kills the job
        error = f"{type(exc).__name__}: {exc}"

    if error:
        limitations.append(
            f"Web research was unavailable for this run ({error}); the report is based on the "
            f"remaining channels."
        )
    await _embed_passages(ctx, passages)
    return await _finalise_channel(
        ctx, Channel.WEB, EventType.WEB_RESEARCH_COMPLETED, sources, documents, passages,
        limitations, error,
    )


# ───────────────────────────── reddit ──────────────────────────────────────


async def reddit_research_node(ctx: JobContext, state: ResearchState) -> dict:
    plan = state["plan"]
    sources: list[Source] = []
    documents: list[Document] = []
    passages: list[Passage] = []
    limitations: list[str] = []
    error: str | None = None

    try:
        ctx.budget.check_deadline()
        posts = await ctx.providers.reddit.search_many(plan.reddit_queries, limit_per_query=10)
        if not posts:
            limitations.append("Reddit search returned no discussions for this product.")
        for post in posts:
            ctx.budget.check_deadline()
            if ctx.budget.sources_exhausted():
                break
            if not ctx.budget.take_page(post.url):
                continue
            try:
                comments = await ctx.providers.reddit.fetch_comments(post, limit=20)
            except Exception as exc:  # noqa: BLE001
                log.info("reddit comment fetch failed for %s: %s", post.url, exc)
                sources.append(_failed_source(Channel.REDDIT, post.url, post.title, str(exc)))
                continue
            body_parts = [post.title, post.selftext]
            body_parts.extend(comment.body for comment in comments if comment.body.strip())
            text = "\n\n".join(part.strip() for part in body_parts if part and part.strip())
            if len(text.split()) < 20:
                continue
            record = _make_records(
                ctx,
                channel=Channel.REDDIT,
                url=post.url,
                title=post.title,
                text=text,
                source_type=SourceType.FORUM_POST,
                authority=0.45 if post.score < 200 else 0.55,
                first_hand=True,
                published_at=post.created_at,
            )
            if record is None:
                break
            ctx.budget.take_source()
            source, doc, chunks = record
            sources.append(source)
            documents.append(doc)
            passages.extend(chunks)
    except ProviderError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    if error:
        limitations.append(
            f"Reddit research was unavailable for this run ({error}); the report is based on the "
            f"remaining channels."
        )
    await _embed_passages(ctx, passages)
    return await _finalise_channel(
        ctx, Channel.REDDIT, EventType.REDDIT_RESEARCH_COMPLETED, sources, documents, passages,
        limitations, error,
    )


# ───────────────────────────── youtube ─────────────────────────────────────


async def youtube_research_node(ctx: JobContext, state: ResearchState) -> dict:
    plan = state["plan"]
    sources: list[Source] = []
    documents: list[Document] = []
    passages: list[Passage] = []
    limitations: list[str] = []
    error: str | None = None

    try:
        ctx.budget.check_deadline()
        videos = await ctx.providers.youtube.search_many(plan.youtube_queries, limit_per_query=5)
        if not videos:
            limitations.append("YouTube search returned no videos for this product.")
        for video in videos:
            ctx.budget.check_deadline()
            if ctx.budget.sources_exhausted():
                break
            if not ctx.budget.take_page(video.url):
                continue
            try:
                transcript = await ctx.providers.youtube.fetch_transcript(video)
            except Exception as exc:  # noqa: BLE001
                log.info("transcript fetch failed for %s: %s", video.url, exc)
                transcript = ""
            if not transcript.strip():
                limitations.append(
                    f"No transcript was available for the video {video.title!r}; only its "
                    f"description was analysed."
                )
            text = "\n\n".join(
                part.strip()
                for part in (video.title, video.description, transcript)
                if part and part.strip()
            )
            if len(text.split()) < 20:
                continue
            record = _make_records(
                ctx,
                channel=Channel.YOUTUBE,
                url=video.url,
                title=video.title,
                text=text,
                source_type=SourceType.VIDEO_REVIEW,
                authority=0.65 if transcript.strip() else 0.4,
                first_hand=True,
                published_at=video.published_at,
            )
            if record is None:
                break
            ctx.budget.take_source()
            source, doc, chunks = record
            sources.append(source)
            documents.append(doc)
            passages.extend(chunks)
    except ProviderError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    if error:
        limitations.append(
            f"YouTube research was unavailable for this run ({error}); the report is based on "
            f"the remaining channels."
        )
    await _embed_passages(ctx, passages)
    return await _finalise_channel(
        ctx, Channel.YOUTUBE, EventType.YOUTUBE_RESEARCH_COMPLETED, sources, documents, passages,
        limitations, error,
    )
