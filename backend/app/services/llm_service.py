"""LLM access via Ollama (local, free).

Streams chat completions token-by-token. The only LLM-vendor-specific code in
the app lives here — swapping Ollama for an OpenAI/Anthropic API in production
is a change to this one module, nothing else.

Observability: every call produces a `gen_ai.chat {model}` span that follows
the OpenTelemetry GenAI semantic conventions (gen_ai.system, .request.model,
.usage.input_tokens, etc.) plus Ollama-specific timing attributes
(prompt_eval, eval, load) and a `gen_ai.first_token` span event marking TTFT.
A single Jaeger trace is enough to answer "why was that /ask slow?".
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx
from opentelemetry import trace

from app.config import settings
from app.observability import metrics

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)


def _record_completion(
    span,
    model: str,
    started: float,
    final: dict,
    outcome: str,
) -> None:
    """Attach final attributes + observe Prometheus histograms for a chat call.

    Called from the `finally` of `stream_chat` so it runs whether the stream
    completed normally, raised, or was cancelled. Histograms tied to the
    Ollama `done` frame are only observed when that frame was actually
    received — otherwise we'd skew them with synthetic zeros.
    """
    wall = time.perf_counter() - started
    span.set_attribute("llm.outcome", outcome)
    span.set_attribute("llm.ollama.wall_seconds", wall)

    metrics.llm_requests_total.labels(model=model, outcome=outcome).inc()
    metrics.llm_generation_seconds.labels(model=model).observe(wall)

    if not final:
        # Stream ended before Ollama's `done` frame — no token counts to record.
        return

    load_s = final.get("load_duration", 0) / 1e9
    prompt_eval_s = final.get("prompt_eval_duration", 0) / 1e9
    eval_s = final.get("eval_duration", 0) / 1e9
    prompt_tokens = final.get("prompt_eval_count", 0)
    tokens = final.get("eval_count", 0)
    tok_per_s = (tokens / eval_s) if eval_s else 0.0

    # GenAI semantic-convention attributes (input_tokens / output_tokens are
    # the current names; some UIs still display the old prompt/completion).
    span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", tokens)
    span.set_attribute("gen_ai.usage.total_tokens", prompt_tokens + tokens)
    # Ollama-specific timing breakdown — this is what makes the span
    # diagnostically useful. prompt_eval is usually the dominant slice on CPU.
    span.set_attribute("llm.ollama.load_seconds", load_s)
    span.set_attribute("llm.ollama.prompt_eval_seconds", prompt_eval_s)
    span.set_attribute("llm.ollama.eval_seconds", eval_s)
    span.set_attribute("llm.ollama.tokens_per_second", tok_per_s)

    metrics.llm_tokens_generated_total.labels(model=model).inc(tokens)
    metrics.llm_prompt_eval_seconds.labels(model=model).observe(prompt_eval_s)
    metrics.llm_eval_seconds.labels(model=model).observe(eval_s)
    if prompt_tokens:
        metrics.llm_prompt_tokens.labels(model=model).observe(prompt_tokens)

    logger.info(
        "llm completion: model=%s outcome=%s prompt_tokens=%d output_tokens=%d "
        "wall=%.2fs load=%.2fs prompt_eval=%.2fs generate=%.2fs (%.1f tok/s)",
        model, outcome, prompt_tokens, tokens, wall, load_s, prompt_eval_s,
        eval_s, tok_per_s,
    )


async def stream_chat(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
) -> AsyncIterator[str]:
    """Yield answer text chunks as the model generates them.

    Ollama's /api/chat with stream=true returns newline-delimited JSON; each
    line carries an incremental `message.content`. We re-yield just the text so
    the router can forward it to the browser as SSE.
    """
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "options": {"temperature": temperature},
    }

    url = f"{settings.ollama_host}/api/chat"
    # Generation on CPU can be slow — generous read timeout, no total timeout.
    timeout = httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
    model = settings.ollama_model

    # Span lives across the whole stream — yields don't exit the with-block,
    # so Jaeger gets one span per chat covering retrieval-to-final-token, with
    # the child `POST /api/chat` from httpx autoinstrumentation nested inside.
    with _tracer.start_as_current_span(f"gen_ai.chat {model}") as span:
        span.set_attribute("gen_ai.system", "ollama")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.request.temperature", temperature)
        span.set_attribute("gen_ai.request.streaming", True)
        span.set_attribute("llm.prompt.system_chars", len(system))
        span.set_attribute("llm.prompt.user_chars", len(user))

        started = time.perf_counter()
        first_token_at: float | None = None
        final: dict = {}
        outcome = "cancelled"  # default — overwritten on success/error
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = obj.get("message", {}).get("content", "")
                        if token:
                            if first_token_at is None:
                                first_token_at = time.perf_counter()
                                ttft = first_token_at - started
                                # The single most useful event on this span — marks
                                # the moment of first byte, splitting the timeline
                                # into "thinking…" (TTFT) and "streaming" (rest).
                                span.add_event(
                                    "gen_ai.first_token",
                                    {"elapsed_seconds": ttft},
                                )
                                metrics.llm_time_to_first_token_seconds.labels(
                                    model=model
                                ).observe(ttft)
                            yield token
                        if obj.get("done"):
                            final = obj  # carries Ollama's timing counters
                            outcome = "success"
                            break
        except Exception as exc:
            outcome = "error"
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            logger.exception("llm completion failed — model=%s", model)
            raise
        finally:
            # Runs on success, error, AND cancellation (client disconnect, since
            # the surrounding async generator can be aclose()'d mid-stream). This
            # is what keeps the metrics + trace attributes honest — without it,
            # an early disconnect would silently drop the entire completion record.
            _record_completion(span, model, started, final, outcome)
