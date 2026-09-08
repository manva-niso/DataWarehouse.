# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install production dependencies
RUN uv sync --frozen --no-dev --no-cache

# Final lightweight runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Install minimal runtime tools (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment / installed dependencies from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application source code
COPY app/ ./app/
COPY dbio/ ./dbio/
COPY marts/ ./marts/
COPY staging/ ./staging/
COPY warehouse/ ./warehouse/
COPY orchestration/ ./orchestration/
COPY export/ ./export/
COPY ingestion/ ./ingestion/
COPY config/ ./config/
COPY pyproject.toml ./

# Ensure storage directories exist
RUN mkdir -p /app/exports /app/.streamlit

# Streamlit configuration for production
RUN echo '\
[server]\n\
port = 8501\n\
address = "0.0.0.0"\n\
headless = true\n\
enableCORS = false\n\
enableXsrfProtection = true\n\
maxUploadSize = 10\n\
[browser]\n\
gatherUsageStats = false\n\
' > /app/.streamlit/config.toml

# Expose Streamlit default port
EXPOSE 8501

# Health check to ensure Streamlit server is responsive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Launch Streamlit application
CMD ["streamlit", "run", "app/Home.py"]
