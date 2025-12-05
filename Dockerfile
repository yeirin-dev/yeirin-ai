# ============================================
# Yeirin-AI Backend - Production Dockerfile
# Python 3.11 + FastAPI + uv + Playwright
# ============================================

# Stage 1: Build
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files and create empty README for build
COPY pyproject.toml uv.lock* ./
RUN touch README.md

# Install dependencies (not editable for production)
RUN uv sync --frozen --no-dev --no-editable

# Stage 2: Production
FROM python:3.11-slim AS production

WORKDIR /app

# Install runtime dependencies (for Playwright and PDF processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Font dependencies
    fonts-liberation \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY pyproject.toml uv.lock* ./
COPY yeirin_ai/ ./yeirin_ai/

# Install Playwright browsers
ENV PATH="/app/.venv/bin:$PATH"
RUN playwright install chromium

# Create non-root user
RUN groupadd -r yeirinai && useradd -r -g yeirinai yeirinai && \
    chown -R yeirinai:yeirinai /app

# Switch to non-root user
USER yeirinai

# Set environment
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Start application
CMD ["uvicorn", "yeirin_ai.main:app", "--host", "0.0.0.0", "--port", "8001"]
