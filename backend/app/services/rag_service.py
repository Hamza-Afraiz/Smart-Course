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
from app.models.user import User
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


# ── Instructor content generation (Week 5 extension) ─────────────────────────
# Same RAG pipeline as Q&A — different system prompts for summary vs quiz.

_SUMMARY_SYSTEM = (
    "You are SmartCourse's instructor assistant. Summarize lesson or course "
    "content clearly for instructors preparing materials. Use ONLY the context "
    "below — do not invent facts. Prefer concise bullet points. Mention lesson "
    "titles when useful."
)

_QUIZ_SYSTEM = (
    "You are SmartCourse's instructor assistant. Create multiple-choice quiz "
    "questions ONLY from the provided context. Never invent facts or add "
    "preamble, closing remarks, or sections outside the required format."
)

_QUIZ_QUESTION_BLOCK = """\
### Question {n}
**Question:** <question text>
- A) <option>
- B) <option>
- C) <option>
- D) <option>
**Correct answer:** <A|B|C|D>
**Explanation:** <one line citing the lesson title>"""


def build_generation_prompts(
    *,
    kind: str,
    scope: str,
    context: str,
) -> tuple[str, str, float]:
    """Return (system_prompt, user_prompt, temperature) for instructor generation."""
    if kind == "summary":
        return (
            _SUMMARY_SYSTEM,
            (
                f"Context from {scope}:\n\n{context}\n\n"
                "Write a clear summary of the key points an instructor should "
                "emphasize. Use only the context above."
            ),
            0.2,
        )

    format_example = _QUIZ_QUESTION_BLOCK.format(n=1)
    return (
        _QUIZ_SYSTEM,
        (
            f"Context from {scope}:\n\n{context}\n\n"
            "Create up to 5 multiple-choice quiz questions for students using "
            "ONLY the context above.\n\n"
            "Use exactly this markdown structure for each question (number 1 through 5). "
            "Do not add any text before the first question or after the last explanation.\n\n"
            f"{format_example}"
        ),
        0.1,
    )

_COURSE_SUMMARY_QUERY = (
    "Main topics, concepts, and learning objectives covered in this course"
)


async def _hits_for_generation(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID | None,
) -> list[dict]:
    """Context for instructor generation — all chunks for one lesson, or top-K for course."""
    if lesson_id is not None:
        rows = await search_repo.list_chunks_for_lesson(
            db, lesson_id=lesson_id, course_id=course_id
        )
        return [
            {
                "lesson_id": row["lesson_id"],
                "lesson_title": row["lesson_title"],
                "text": row["text"],
                "similarity": 1.0,
            }
            for row in rows
        ]
    return await retrieve(
        db,
        question=_COURSE_SUMMARY_QUERY,
        course_id=course_id,
        top_k=settings.rag_top_k,
    )


async def generate_stream(
    db: AsyncSession,
    *,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID | None,
    kind: str,
    actor: User,
) -> AsyncIterator[str]:
    """Stream a lesson/course summary or quiz for the course owner (instructor/admin).

    Caller must verify ownership before streaming (router does this so 403/404
    are normal HTTP errors, not SSE payloads).
    """
    _ = actor  # reserved for future audit logging

    with _tracer.start_as_current_span("rag.generate") as span:
        span.set_attribute("rag.course_id", str(course_id))
        span.set_attribute("rag.generation_kind", kind)
        if lesson_id:
            span.set_attribute("rag.lesson_id", str(lesson_id))

        hits = await _hits_for_generation(db, course_id=course_id, lesson_id=lesson_id)
        span.set_attribute("rag.hits_used", len(hits))

    if not hits:
        yield (
            "No indexed lesson content found. Publish the course first so the "
            "publishing workflow can extract, chunk, and embed the material."
        )
        return

    with _tracer.start_as_current_span("rag.build_prompt") as span:
        context, trimmed_count = _build_context(hits)
        scope = hits[0]["lesson_title"] if lesson_id else "this course"
        system, user_prompt, temperature = build_generation_prompts(
            kind=kind, scope=scope, context=context
        )
        span.set_attribute("rag.context_chars", len(context))
        span.set_attribute("rag.prompt_chars", len(user_prompt) + len(system))
        span.set_attribute("rag.chunks_trimmed", trimmed_count)

    async for token in llm_service.stream_chat(
        system=system, user=user_prompt, temperature=temperature
    ):
        yield token
