# Builder stage: Compile the flux wheel and dependencies
ARG PYTHON_IMAGE_VERSION=3.12
# Latest stable version as of May 2025
ARG POETRY_VERSION=1.8.3
FROM python:${PYTHON_IMAGE_VERSION}-slim AS builder

ARG POETRY_VERSION

# Install Poetry and build dependencies
RUN pip install --no-cache-dir poetry==${POETRY_VERSION} && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only dependency files first for layer caching
COPY pyproject.toml poetry.lock ./

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-dev --no-root

# Copy source code and build wheel
COPY flux/ ./flux/
COPY README.md ./
RUN poetry build && \
    VERSION=$(poetry version -s) && \
    echo "VERSION=${VERSION}" > version.env

# Runtime stage: Create a lean image for deployment
FROM python:${PYTHON_IMAGE_VERSION}-slim AS runtime

ARG EXTRA_PACKAGES=""

WORKDIR /app

# Install runtime dependencies (SQLite, PostgreSQL, Redis, RabbitMQ, cloud SDKs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir \
    psycopg2-binary \
    redis \
    pika \
    boto3 \
    google-cloud-functions \
    "${EXTRA_PACKAGES}"

# Copy artifacts from builder
COPY --from=builder /app/version.env /app/dist/*.whl ./
COPY flux.toml ./

# Install flux wheel
RUN . ./version.env && pip install --no-cache-dir flux_core-${VERSION}-py3-none-any.whl

# Create non-root user
RUN useradd -m fluxuser && chown -R fluxuser:fluxuser /app
USER fluxuser

# Set up flux directories
RUN mkdir -p .flux/.workflows && touch .flux/.workflows/__init__.py

# Environment variables for flux configuration
ENV FLUX_DATABASE_URL=sqlite:///.flux/flux.db \
    FLUX_CACHE_BACKEND=redis \
    FLUX_CACHE_REDIS_HOST=redis \
    FLUX_SERVER_PORT=8000

# Expose API port
EXPOSE 8000

# Health check for API server
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${FLUX_SERVER_PORT}/health || exit 1

# Entrypoint to start flux API server
ENTRYPOINT ["flux", "start", ".flux/.workflows"]
