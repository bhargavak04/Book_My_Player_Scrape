FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/output /app/logs /app/input

# Copy application code
COPY scraper.py /app/scraper.py
COPY config.py /app/config.py

# Create default configuration
ENV AUTO_SAVE_INTERVAL=1000
ENV REQUEST_DELAY=1.0
ENV INPUT_FILE=/app/input/urls.xlsx
ENV URL_COLUMN=url
ENV START_FROM=0

# Create non-root user for security
RUN useradd -m -u 1000 scraper && \
    chown -R scraper:scraper /app
USER scraper

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/logs') else 1)"

# Default command
CMD ["python", "scraper.py"]
