"""RAG orchestration: retrieve grounded context, then generate an answer.

Flow:
  1. embed the question (reuse the Week 4 embedding service)
  2. ANN search lesson_chunks (reuse search_repo) — scoped to the course
  3. drop chunks below a similarity floor (so off-topic questions don't get
     answered from irrelevant text)
  4. build a grounded prompt: "answer ONLY from this context; else say you
     don't know" — this is what keeps the LLM from hallucinating
  5. stream the answer from the LLM

The retrieval half is identical to semantic search; RAG just adds the LLM on
top of the same chunks.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import tiktoken
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories import search_repo
from app.services import embedding_service, llm_service

_tracer = trace.get_tracer(__name__)
_ENCODER = tiktoken.get_encoding("cl100k_base")

_SYSTEM_PROMPT = (
    "You are SmartCourse's teaching assistant. The context below contains "
    "excerpts from this course's lessons — treat it as the authoritative "
    "source and answer the student's question from it, even if the excerpts "
    "are brief: quote or paraphrase what's relevant. Do NOT pull in outside "
    "knowledge or invent details beyond the context. Only if the context "
    "contains nothing at all related to the question should you say you don't "
    "have that information in this course. Keep answers concise and mention the "
    "lesson title when useful."
)


async def retrieve(
    db: AsyncSession, *, question: str, course_id: uuid.UUID, top_k: int
) -> list[dict]:
    """Top-K chunks for the question, scoped to one course, similarity-filtered."""
    with _tracer.start_as_current_span("rag.retrieve") as span:
        span.set_attribute("rag.course_id", str(course_id))
        span.set_attribute("rag.top_k", top_k)
        span.set_attribute("rag.question_chars", len(question))
        span.set_attribute("rag.min_similarity", settings.rag_min_similarity)

        vectors = await embedding_service.embed([question])
        hits = await search_repo.search_chunks(
            db, query_vector=vectors[0], course_id=course_id, limit=top_k
        )
        filtered = [h for h in hits if h["similarity"] >= settings.rag_min_similarity]

        span.set_attribute("rag.hits_raw", len(hits))
        span.set_attribute("rag.hits_filtered", len(filtered))
        if filtered:
            span.set_attribute("rag.top_similarity", filtered[0]["similarity"])
        return filtered


def _trim_chunk_text(text: str, max_tokens: int) -> tuple[str, bool]:
    """Keep the leading tokens of a chunk; prefill cost scales with prompt length."""
    tokens = _ENCODER.encode(text)
    if len(tokens) <= max_tokens:
        return text, False
    trimmed = _ENCODER.decode(tokens[:max_tokens]).rstrip()
    return f"{trimmed}…", True


def _build_context(hits: list[dict]) -> tuple[str, int]:
    """Format retrieved chunks for the LLM prompt, trimming each to a token cap."""
    blocks: list[str] = []
    trimmed_count = 0
    max_tokens = settings.rag_max_chunk_tokens
    for h in hits:
        excerpt, was_trimmed = _trim_chunk_text(h["text"], max_tokens)
        if was_trimmed:
            trimmed_count += 1
        blocks.append(f"[From lesson: {h['lesson_title']}]\n{excerpt}")
    return "\n\n---\n\n".join(blocks), trimmed_count


async def answer_stream(
    db: AsyncSession, *, question: str, course_id: uuid.UUID
) -> AsyncIterator[str]:
    """Yield the grounded answer token-by-token.

    First yields nothing special; if no relevant chunks are found, yields a
    single canned 'not covered' message and stops (no LLM call — saves the
    round trip and guarantees we never hallucinate on off-topic questions).
    """
    hits = await retrieve(
        db, question=question, course_id=course_id, top_k=settings.rag_top_k
    )

    if not hits:
        yield (
            "I don't have information about that in this course. "
            "Try rephrasing, or ask about a topic the lessons cover."
        )
        return

    # Sub-ms span — kept because the attributes are the audit trail for what
    # the model actually saw (context_chars correlates with prompt_eval time).
    with _tracer.start_as_current_span("rag.build_prompt") as span:
        context, trimmed_count = _build_context(hits)
        user_prompt = (
            f"Context from the course:\n\n{context}\n\n"
            f"Student question: {question}\n\n"
            f"Answer using only the context above."
        )
        span.set_attribute("rag.context_chars", len(context))
        span.set_attribute("rag.prompt_chars", len(user_prompt) + len(_SYSTEM_PROMPT))
        span.set_attribute("rag.hits_used", len(hits))
        span.set_attribute("rag.chunks_trimmed", trimmed_count)
        span.set_attribute("rag.max_chunk_tokens", settings.rag_max_chunk_tokens)

    async for token in llm_service.stream_chat(
        system=_SYSTEM_PROMPT, user=user_prompt
    ):
        yield token
