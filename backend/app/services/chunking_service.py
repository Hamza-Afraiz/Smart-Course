"""Token-aware, sentence-boundary-respecting chunker for lesson text.

Tokens (not words or characters) because the LLM in Week 5 will count tokens
when fitting context. tiktoken with `cl100k_base` is the GPT-4-class tokenizer
and a good approximation of what any modern model considers a token.

Strategy:
  - Split source into "sentence-ish" pieces (period/?/! followed by whitespace,
    plus paragraph breaks). Keeps semantic units together.
  - Greedily pack sentences into a chunk until adding the next one would
    exceed `max_tokens`.
  - Maintain an `overlap_tokens` suffix from the previous chunk at the start
    of the next, so context across boundaries isn't lost.

For long single sentences (e.g. a code block, a malformed paragraph), we fall
back to a hard token split inside that sentence to avoid one chunk that's
many times larger than the limit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

ENCODER = tiktoken.get_encoding("cl100k_base")

# Sentence-ish boundaries: end-punct + whitespace OR a blank line.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


@dataclass
class Chunk:
    text: str
    token_count: int


def chunk_text(
    text: str,
    *,
    max_tokens: int = 400,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Split source `text` into token-bounded chunks with overlap."""
    text = (text or "").strip()
    if not text:
        return []

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current_tokens: list[int] = []

    for sentence in sentences:
        s_tokens = ENCODER.encode(sentence)

        # If a single sentence is longer than the budget, hard-split it.
        if len(s_tokens) > max_tokens:
            _flush(chunks, current_tokens)
            current_tokens = []
            for i in range(0, len(s_tokens), max_tokens - overlap_tokens):
                window = s_tokens[i : i + max_tokens]
                chunks.append(
                    Chunk(text=ENCODER.decode(window), token_count=len(window))
                )
            continue

        # Adding this sentence overflows → flush, start next chunk with overlap.
        if len(current_tokens) + len(s_tokens) > max_tokens:
            _flush(chunks, current_tokens)
            current_tokens = current_tokens[-overlap_tokens:] if overlap_tokens else []

        current_tokens.extend(s_tokens)

    _flush(chunks, current_tokens)
    return chunks


def _flush(out: list[Chunk], tokens: list[int]) -> None:
    if not tokens:
        return
    out.append(Chunk(text=ENCODER.decode(tokens).strip(), token_count=len(tokens)))
