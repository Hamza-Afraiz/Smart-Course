from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown env vars — don't crash on unrelated vars
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    secret_key: str
    access_token_expire_minutes: int = 60

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    database_url: str  # must use postgresql+psycopg:// scheme

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── RabbitMQ ──────────────────────────────────────────────────────────────
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "amqp://guest:guest@localhost:5672/"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Temporal (Week 2) ─────────────────────────────────────────────────────
    temporal_host: str = "localhost:7233"

    # ── Kafka (Week 3) ────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "localhost:9094"

    # ── MongoDB (Week 3 — raw event log) ──────────────────────────────────────
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "smartcourse"

    # ── Tracing (Week 3 — OpenTelemetry → Jaeger) ─────────────────────────────
    # empty string = tracing disabled (e.g. running tests or host dev without Jaeger)
    otel_exporter_otlp_endpoint: str = ""

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


# single instance imported everywhere — never instantiate Settings() again
settings = Settings()
