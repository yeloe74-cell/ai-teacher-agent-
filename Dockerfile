# Dockerfile
# AI Teacher Bot - Docker Image

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project files
COPY . .

# Create required directories
RUN mkdir -p logs data

# Run migrations on startup
RUN python scripts/run_migrations.py || true

# Expose no ports (Telegram bot doesn't need ports)
# EXPOSE none

# Run bot
CMD ["python", "main.py"]
