"""W3C traceparent propagation across async boundaries (outbox → Kafka → workers)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from opentelemetry import context as otel_context
from opentelemetry.propagate import extract, inject

T = TypeVar("T")


def inject_traceparent() -> str | None:
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier.get("traceparent")


@asynccontextmanager
async def use_traceparent(traceparent: str | None) -> AsyncIterator[None]:
    if not traceparent:
        yield
        return
    token = otel_context.attach(extract({"traceparent": traceparent}))
    try:
        yield
    finally:
        otel_context.detach(token)


async def run_with_traceparent(
    traceparent: str | None,
    coro_factory: Callable[[], Coroutine[Any, Any, T]],
) -> T:
    async with use_traceparent(traceparent):
        return await coro_factory()
