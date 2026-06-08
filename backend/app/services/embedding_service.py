"""Local CPU embedding via sentence-transformers — no API key, no network.

The model (`all-MiniLM-L6-v2`, 384-dim) is downloaded on first use into the
HuggingFace cache. To avoid a slow first request in production, the chunking
activity calls `warm_up()` at process start; subsequent encodes reuse the
loaded model.

Lazy module-level singleton so we don't load the model in test paths or
processes that never call it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("loading embedding model: %s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME, device="cpu")
        logger.info("embedding model loaded")
    return _model


def warm_up() -> None:
    """Eagerly load + run one encode so first user request is fast."""
    _get_model().encode(["warm-up"], show_progress_bar=False)


def embed_sync(texts: list[str]) -> list[list[float]]:
    """Encode a batch of texts; returns one 384-dim list per input."""
    if not texts:
        return []
    model = _get_model()
    arr = model.encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=True,  # cosine distance assumes unit-length
        convert_to_numpy=True,
    )
    return arr.tolist()


async def embed(texts: list[str]) -> list[list[float]]:
    """Async-friendly wrapper — runs the CPU work in a thread pool so it
    doesn't block the event loop in async services (relay, consumers, API).
    """
    if not texts:
        return []
    # One span per encode call. Closes the previously-invisible gap between
    # `SELECT users` and `SELECT lesson_chunks` on /ask traces in Jaeger.
    with _tracer.start_as_current_span("rag.embed") as span:
        span.set_attribute("rag.embedding.model", MODEL_NAME)
        span.set_attribute("rag.embedding.dim", EMBEDDING_DIM)
        span.set_attribute("rag.embedding.batch_size", len(texts))
        span.set_attribute("rag.embedding.total_chars", sum(len(t) for t in texts))
        return await asyncio.to_thread(embed_sync, texts)
