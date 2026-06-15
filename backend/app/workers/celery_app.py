"""Celery application instance.

Celery is our **task executor** layer — separate from Kafka, which distributes
events. The flow:
    Kafka event → bridge consumer dedupes → Celery task enqueued (RabbitMQ)
                                            → Celery worker picks it up and runs

The bridge consumer and the Celery worker are independent processes. Tasks
are declared in `app.tasks.*` and auto-discovered via `include=`.
"""

from celery import Celery
from celery.signals import setup_logging, worker_init

from app.config import settings


@setup_logging.connect
def _configure_celery_logging(**_kwargs):
    """Tell Celery to use our JSON logger + tracing instead of its own format."""
    from app.observability.logging import configure_json_logging
    from app.observability.tracing import configure_tracing
    configure_json_logging(service_name="celery-worker")
    configure_tracing(service_name="celery-worker")


@worker_init.connect
def _start_metrics(**_kwargs):
    """Expose /metrics from the worker's main process so Prometheus sees
    up{job="celery-worker"}."""
    from app.observability.metrics_server import start_metrics_server
    start_metrics_server()


celery_app = Celery(
    "smart_course",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.welcome_email", "app.tasks.reindex_course"],
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=60,           # hard kill after 60s
    task_soft_time_limit=45,      # raises SoftTimeLimitExceeded — task can clean up
    task_acks_late=True,          # ack only on success — redelivered on worker crash
    worker_prefetch_multiplier=1, # don't hoard tasks; fair distribution across workers
    task_reject_on_worker_lost=True,
)
