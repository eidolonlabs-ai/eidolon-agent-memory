FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

COPY alembic.ini .
COPY alembic/ alembic/

# ------- server stage -------
FROM base AS server
CMD ["python", "-m", "eidolon_agent_memory.server"]

# ------- worker stage -------
FROM base AS worker
CMD ["python", "-m", "eidolon_agent_memory.worker"]
