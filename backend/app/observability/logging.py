"""Structured JSON logging — one log line per record, parseable by anything.

Output shape:

    {"asctime": "2026-05-19 11:38:52,021",
     "level":   "INFO",
     "logger":  "app.services.enrollment_service",
     "message": "...",
     "service": "api",                 ← added by `service_name` arg
     "trace_id": "...",                ← populated by OpenTelemetry (later chunk)
     ...extras...}

JSON logs are useless to humans tailing a single container, but invaluable
to log aggregators (Loki, Elastic, Datadog, CloudWatch). Once we add OTel,
the `trace_id` field is what stitches a single request's logs across every
service it touched.
"""

import logging
from typing import Any

from pythonjsonlogger import jsonlogger


class _TraceContextFilter(logging.Filter):
    """Stamp the active OpenTelemetry trace/span id onto every log record.

    This is the bridge between the logs pillar and the traces pillar: the same
    `trace_id` that identifies a request's waterfall in Jaeger appears on every
    JSON log line emitted while that span is active. Filter into a log shipper
    by trace_id and you get every line for one request, across services.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = span_id = None
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx and ctx.is_valid:
                trace_id = format(ctx.trace_id, "032x")
                span_id = format(ctx.span_id, "016x")
        except Exception:
            pass
        record.trace_id = trace_id
        record.span_id = span_id
        return True


class _JsonFormatter(jsonlogger.JsonFormatter):
    """Always include `service` and reformat the level field to a string."""

    def __init__(self, service_name: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._service = service_name

    def add_fields(self, log_record, record, message_dict):  # type: ignore[override]
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("service", self._service)
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)


def configure_json_logging(service_name: str, level: int = logging.INFO) -> None:
    """Replace any existing handlers with a single JSON-formatted stream handler.

    Call once at process startup (api lifespan, each worker's _run()).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter(
        service_name=service_name,
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s",
    ))
    handler.addFilter(_TraceContextFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Force libraries that install their own handlers (uvicorn especially)
    # to propagate to root — so their records go through OUR JSON formatter.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "celery", "celery.task"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True

    # SQLAlchemy is chatty at INFO; quiet the noisy ones but keep them tweakable
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    logging.getLogger("aiokafka.consumer.group_coordinator").setLevel(logging.WARNING)
