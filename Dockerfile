FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# pg_dump must match the server major version (PostgreSQL 16) for nightly backups.
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates lsb-release \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
 && apt-get purge -y gnupg lsb-release && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY bots ./bots
COPY migrations ./migrations
COPY tests ./tests

RUN pip install --upgrade pip && pip install . && pip install pytest pytest-asyncio httpx

# Run as an unprivileged user; the private storage folder must be writable.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /app/private_storage && chown -R app:app /app
USER app

EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
