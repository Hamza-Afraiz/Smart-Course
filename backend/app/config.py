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
    cache_enabled: bool = True  # best-effort hot-path cache; turned off under test

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

    # ── Object storage (Week 4 — MinIO in dev, R2/S3 in prod) ─────────────────
    # Two endpoints on purpose: the browser signs against the PUBLIC one
    # (reachable from the host), workers use the INTERNAL one (compose DNS) for
    # direct get_object. Swapping MinIO → R2/S3 in prod is just env-var changes.
    s3_internal_endpoint: str = "http://minio:9000"    # server-side (api/worker inside compose)
    s3_public_endpoint: str = "http://localhost:9000"   # browser-facing presigned URLs
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "smartcourse-media"
    s3_region: str = "us-east-1"
    s3_presign_ttl: int = 3600  # presigned URL lifetime (seconds)

    # ── LLM / RAG (Week 5 — Ollama local in dev, swap to API in prod) ─────────
    ollama_host: str = "http://localhost:11434"   # docker-compose → http://ollama:11434
    ollama_model: str = "llama3.2:1b"             # smaller = ~3x faster on CPU; RAG carries the facts
    rag_top_k: int = 3                            # fewer chunks → shorter prompt → less prefill time
    rag_min_similarity: float = 0.25              # drop weak matches; keeps context focused
    rag_max_chunk_tokens: int = 200               # cap each excerpt — prefill scales with prompt length

    # ── SMTP (Tier 2 — Mailhog in dev) ────────────────────────────────────────
    smtp_enabled: bool = True
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_use_tls: bool = False
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "SmartCourse <noreply@smartcourse.local>"

    # ── Dev seed users (created once by migrate) ──────────────────────────────
    seed_dev_users: bool = True
    dev_admin_email: str = "admin@smartcourse.local"
    dev_admin_password: str = "SmartCourseAdmin1!"
    dev_instructor_email: str = "instructor@smartcourse.local"
    dev_instructor_password: str = "SmartCourseInstruct1!"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


# single instance imported everywhere — never instantiate Settings() again
settings = Settings()
