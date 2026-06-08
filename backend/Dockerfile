# Single image for the whole backend. docker-compose runs it in three roles
# (migrate / api / worker) by overriding `command:` — same code, same deps,
# guaranteed-identical version across the API and the Temporal worker.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# psycopg 3 loads libpq at runtime; ffmpeg decodes video → audio for Whisper
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# deps first — this layer stays cached when only app code changes.
# torch is big (~150MB); bigger pip timeouts + retries make sure slow
# networks don't fail the build mid-download.
COPY requirements.txt .
RUN pip install --timeout 600 --retries 10 -r requirements.txt

# baked-in code. docker-compose bind-mounts ./app over this for dev hot-reload,
# but the image is self-contained for a plain `docker run`.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# default role; compose overrides this per service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
