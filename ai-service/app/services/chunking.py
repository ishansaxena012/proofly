"""Document → passage chunking.

Passages are paragraph-aligned and word-bounded so that every piece of evidence
can be traced back to a contiguous span of text that a source really contained.
"""

from __future__ import annotations

from app.models.domain import Document, Passage
from app.services.heuristics import content_hash, estimate_tokens

TARGET_WORDS = 130
MIN_WORDS = 25
MAX_WORDS = 220


def build_document(source_id: str, raw_text: str) -> Document:
    text = raw_text.strip()
    return Document(
        source_id=source_id,
        raw_text=text,
        content_hash=content_hash(text),
        token_count=estimate_tokens(text),
    )


def split_passages(document: Document) -> list[Passage]:
    paragraphs = [block.strip() for block in document.raw_text.split("\n") if block.strip()]
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_words = 0

    def flush() -> None:
        nonlocal buffer, buffer_words
        if buffer:
            chunks.append("\n".join(buffer).strip())
            buffer = []
            buffer_words = 0

    for paragraph in paragraphs:
        words = paragraph.split()
        if len(words) > MAX_WORDS:
            flush()
            for start in range(0, len(words), TARGET_WORDS):
                chunks.append(" ".join(words[start : start + TARGET_WORDS]))
            continue
        if buffer_words + len(words) > TARGET_WORDS and buffer_words >= MIN_WORDS:
            flush()
        buffer.append(paragraph)
        buffer_words += len(words)
    flush()

    passages: list[Passage] = []
    for position, chunk in enumerate(chunks):
        if len(chunk.split()) < 5:
            continue
        passages.append(
            Passage(
                document_id=document.id,
                source_id=document.source_id,
                text=chunk,
                position=position,
            )
        )
    return passages
