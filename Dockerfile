FROM python:3.14-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.14-slim AS runtime

LABEL maintainer="apartment-notifier-bot"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash botuser

WORKDIR /app

ENV PYTHONPATH=/app

COPY --from=builder /install /usr/local

COPY --chown=botuser:botuser app/ ./app/
COPY --chown=botuser:botuser migrations/ ./migrations/
COPY --chown=botuser:botuser alembic.ini ./alembic.ini

RUN mkdir -p /app/logs && chown botuser:botuser /app/logs

USER botuser

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD pgrep -f "python -m app.main" || exit 1

CMD ["python", "-m", "app.main"]