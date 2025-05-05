FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt /app/

# Install project dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app/

# Create and set up directories
RUN mkdir -p /mnt/data/app /mnt/data/logs \
    && chmod -R 755 /mnt/data

# Run as non-root user
RUN useradd -m app_user \
    && chown -R app_user:app_user /app /mnt/data

USER app_user

# Expose the application port
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Start the application
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}