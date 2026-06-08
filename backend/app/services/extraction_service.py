"""Pull source text from `video` and `pdf` lessons so the chunking pipeline
can treat them the same as `text` lessons.

Design choices:
- **YouTube videos** → fetch existing captions via youtube-transcript-api.
  Vastly faster than running Whisper locally, no model download, no audio
  pipeline. For non-YouTube video URLs, we'd need Whisper — not implemented
  yet; we just log a warning and skip.
- **PDFs** → download with httpx, parse with pypdf. Whole document → one long
  string that the chunker then splits.

All extraction is best-effort: a single bad URL or a video without captions
must not fail the publish workflow. We log the reason and return None; the
activity then skips that lesson.
"""

from __future__ import annotations

import asyncio
import logging
import re
from io import BytesIO

import httpx

logger = logging.getLogger(__name__)

# youtube.com/watch?v=ID  or  youtu.be/ID  or  youtube.com/embed/ID
_YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


# ── PDF ───────────────────────────────────────────────────────────────────────

async def extract_pdf(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
        # pypdf parsing is sync + CPU-bound — push to a thread
        return await asyncio.to_thread(_parse_pdf, r.content)
    except Exception as e:
        logger.warning("pdf extraction failed for %s: %s", url, e)
        return None


def _parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    parts = [(p.extract_text() or "").strip() for p in reader.pages]
    return "\n\n".join(p for p in parts if p)


async def extract_pdf_bytes(data: bytes) -> str | None:
    """PDF text from already-downloaded bytes (uploaded files)."""
    try:
        return await asyncio.to_thread(_parse_pdf, data)
    except Exception as e:
        logger.warning("pdf parse from bytes failed: %s", e)
        return None


async def transcribe_bytes(data: bytes, suffix: str = ".mp4") -> str | None:
    """Whisper transcript from already-downloaded media bytes (uploaded files)."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        return await asyncio.to_thread(_whisper_transcribe, path)
    except Exception as e:
        logger.warning("whisper transcription from bytes failed: %s", e)
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── Video → YouTube transcript, with Whisper fallback for direct URLs ───────

async def extract_video_text(url: str) -> str | None:
    """Two-stage strategy:
      1. If it's a YouTube URL, try fetching existing captions (free, fast).
      2. If that fails OR it's a direct video URL (.mp4 etc.), download the
         file and transcribe with local Whisper (tiny model, CPU).
    """
    m = _YOUTUBE_RE.search(url)
    if m:
        text = await asyncio.to_thread(_fetch_youtube_transcript, m.group(1))
        if text:
            return text
        logger.info(
            "youtube transcript unavailable for %s — falling back to Whisper "
            "(only works for direct video URLs; YouTube blocks audio download here)",
            m.group(1),
        )
        return None  # we can't download YouTube audio in-container

    # Direct video URL — download + Whisper
    return await _transcribe_url(url)


async def _transcribe_url(url: str) -> str | None:
    import tempfile, os

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
    except Exception as e:
        logger.warning("video download failed for %s: %s", url, e)
        return None

    # Write to a temp file so ffmpeg/CTranslate2 can open it by path
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(r.content)
        path = f.name

    try:
        return await asyncio.to_thread(_whisper_transcribe, path)
    except Exception as e:
        logger.warning("whisper transcription failed for %s: %s", url, e)
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


_whisper_model = None


def _get_whisper():
    """Lazy-load the tiny Whisper model once per process."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info("loading Whisper model: tiny (CPU)")
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded")
    return _whisper_model


def _whisper_transcribe(path: str) -> str:
    segments, _info = _get_whisper().transcribe(path, language=None, beam_size=1)
    return " ".join(seg.text.strip() for seg in segments).strip()


def warm_whisper() -> None:
    """Call at worker startup so first publish doesn't pay model-load cost."""
    _get_whisper()


def _fetch_youtube_transcript(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi,
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError:
        logger.warning("youtube-transcript-api not installed; skipping video %s", video_id)
        return None

    try:
        # Prefer English where available; fall back to whatever exists
        segs = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        logger.warning("youtube transcript unavailable for %s: %s", video_id, e.__class__.__name__)
        return None
    except Exception as e:
        # Network blocks, rate limits, anything else — log and skip rather than fail the workflow
        logger.warning("youtube transcript fetch failed for %s: %s", video_id, e)
        return None

    return " ".join(seg["text"].strip() for seg in segs if seg.get("text")).strip()
