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
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt ./

# Install Python dependencies in stages to avoid conflicts
# First install PyTorch CPU version
RUN pip install --no-cache-dir torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cpu

# Then install other dependencies (skip torch lines)
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    pydantic-settings==2.1.0 \
    pydicom==2.4.3 \
    opencv-python-headless==4.8.1.78 \
    Pillow==10.1.0 \
    numpy==1.24.3 \
    pandas==2.1.3 \
    scikit-learn==1.3.2 \
    asyncpg==0.29.0 \
    sqlalchemy==2.0.23 \
    redis==5.0.1 \
    prometheus-client==0.19.0 \
    structlog==23.2.0 \
    python-multipart==0.0.6 \
    python-dotenv==1.0.0 \
    pyyaml==6.0.1 \
    aiofiles==23.2.1 \
    httpx==0.25.2

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
COPY --from=builder --chown=appuser:appuser /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder --chown=appuser:appuser /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser src/ ./src/

# Copy configs directory (now exists in repo)
COPY --chown=appuser:appuser configs/ ./configs/

# Create necessary directories
RUN mkdir -p /app/cache /app/logs /app/models /tmp/app && \
    chown -R appuser:appuser /app /tmp/app

# Environment variables
ENV PYTHONPATH="/app:$PYTHONPATH" \
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

# Create symlinks for python and pip (remove existing if present)
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Install PyTorch with CUDA support (use pip3 explicitly)
RUN pip3 install --no-cache-dir torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118

# Copy application code
COPY --chown=appuser:appuser src/ ./src/

# Copy configs directory (now exists in repo)
COPY --chown=appuser:appuser configs/ ./configs/

# Create directories
RUN mkdir -p /app/cache /app/logs /app/models /tmp/app && \
    chown -R appuser:appuser /app /tmp/app

ENV PYTHONPATH="/app:$PYTHONPATH" \
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
