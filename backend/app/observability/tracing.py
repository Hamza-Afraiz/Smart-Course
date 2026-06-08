"""OpenTelemetry tracing setup.

`configure_tracing(service_name)` wires up a tracer provider that exports
spans to Jaeger over OTLP/gRPC, and auto-instruments the libraries we care
about (FastAPI HTTP handlers, SQLAlchemy queries). Like JSON logging, this is
per-process — every container calls it once at startup with its own name, so
Jaeger can tell the services apart.

Endpoint comes from OTEL_EXPORTER_OTLP_ENDPOINT (set per service in
docker-compose, pointing at the jaeger container). If it's unset or Jaeger is
down, the exporter degrades quietly — spans are dropped, the app keeps serving.
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

logger = logging.getLogger(__name__)

_configured = False


def configure_tracing(service_name: str) -> None:
    """Idempotent. Sets the global tracer provider + OTLP exporter for this process."""
    global _configured
    if _configured:
        return

    if not settings.otel_exporter_otlp_endpoint:
        logger.info("tracing disabled — OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
                insecure=True,  # plaintext gRPC to the local Jaeger collector
            )
        )
    )
    trace.set_tracer_provider(provider)
    _configured = True
    logger.info(
        "tracing enabled — service=%s exporting to %s",
        service_name, settings.otel_exporter_otlp_endpoint,
    )


def instrument_fastapi(app) -> None:
    """Auto-instrument a FastAPI app — one span per request + propagation."""
    if not _configured:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")


def instrument_sqlalchemy(engine) -> None:
    """Auto child-span every SQL statement run through this async engine."""
    if not _configured:
        return
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    # async engines expose the real engine under .sync_engine
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def instrument_httpx() -> None:
    """Auto child-span every outbound httpx request (notably the Ollama LLM call).

    Without this, the assistant's call to Ollama is an invisible gap in the
    trace: the DB span finishes, then nothing until the streamed response ends.
    Instrumenting httpx turns that gap into a named `POST /api/chat` span, so
    Jaeger shows the LLM time explicitly — the dominant cost of a RAG answer.
    """
    if not _configured:
        return
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()
