# Dockerfile for garcold-erp-api with Playwright & FastAPI support

# Use official Playwright Python image based on Ubuntu (includes libexpat, chromium, and all browser deps)
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=2.1.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8000

# Install pip and poetry
RUN python -m pip install --upgrade pip && \
    pip install "poetry==$POETRY_VERSION"

WORKDIR /app

# Copy dependency files first to leverage Docker layer caching
COPY pyproject.toml poetry.lock* /app/

# Install python dependencies
RUN poetry install --no-root --only main

# Copy application source code
COPY . /app/

# Install Chromium browser binary for Playwright
RUN poetry run python -m playwright install chromium

# Expose server port
EXPOSE 8000

# Start application using uvicorn via poetry
CMD ["sh", "-c", "poetry run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
