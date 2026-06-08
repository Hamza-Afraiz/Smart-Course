"""Expose a Prometheus /metrics endpoint from a worker process.

The API gets its /metrics from prometheus-fastapi-instrumentator, but the
long-running workers (relay, consumers, temporal worker, celery worker) have
no HTTP server — so Prometheus couldn't see them at all, and couldn't tell if
one had died. This starts a tiny background HTTP server serving the default
registry, so Prometheus can scrape `up{job="<worker>"}` and alert on it.

start_http_server runs a daemon thread — safe alongside asyncio or Celery.
"""

import logging

from prometheus_client import start_http_server

logger = logging.getLogger(__name__)

DEFAULT_PORT = 9100


def start_metrics_server(port: int = DEFAULT_PORT) -> None:
    try:
        start_http_server(port)
        logger.info("metrics server listening on :%d/metrics", port)
    except Exception as e:
        # never let a metrics port collision take down the worker itself
        logger.warning("could not start metrics server on :%d: %s", port, e)
