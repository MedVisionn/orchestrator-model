# Multi-stage Dockerfile for production-grade X-Ray AI Service
# Optimized for size, security, and performance

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.10-slim AS builder

# Build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Labels (OCI standard)
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.authors="MedScanAI Engineering" \
      org.opencontainers.image.url="https://medscanai.com" \
      org.opencontainers.image.source="https://github.com/MedVisionn/orchestrator-model" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="MedScanAI Inc." \
      org.opencontainers.image.title="X-Ray AI Service" \
      org.opencontainers.image.description="Enterprise-grade AI-powered chest X-ray analysis"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install Python dependencies
RUN poetry install --no-dev --no-root && \
    poetry run pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cpu && \
    poetry cache clear pypi --all

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.10-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser src/ ./src/

# Copy configs directory (now exists in repo)
COPY --chown=appuser:appuser configs/ ./configs/

# Create necessary directories
RUN mkdir -p /app/cache /app/logs /app/models /tmp/app && \
    chown -R appuser:appuser /app /tmp/app

# Environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH" \
    ENVIRONMENT="production" \
    LOG_LEVEL="INFO" \
    MODEL_PATH="/app/models/model.pth" \
    CACHE_DIR="/app/cache" \
    TMP_DIR="/tmp/app"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health/live').raise_for_status()"

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Startup command
CMD ["uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info", \
     "--access-log", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]

# =============================================================================
# Stage 3: Development (optional)
# =============================================================================
FROM builder AS development

# Install dev dependencies
RUN poetry install --with dev

# Install additional dev tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy test files
COPY tests/ ./tests/

# Development command
CMD ["uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--log-level", "debug"]

# =============================================================================
# Stage 4: GPU Runtime (optional)
# =============================================================================
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 AS gpu-runtime

# Install Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Install PyTorch with CUDA support
RUN /app/.venv/bin/pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118

# Copy application code
COPY --chown=appuser:appuser src/ ./src/

# Copy configs directory (now exists in repo)
COPY --chown=appuser:appuser configs/ ./configs/

# Create directories
RUN mkdir -p /app/cache /app/logs /app/models /tmp/app && \
    chown -R appuser:appuser /app /tmp/app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app:$PYTHONPATH" \
    ENVIRONMENT="production" \
    DEVICE="cuda" \
    CUDA_VISIBLE_DEVICES="0"

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
