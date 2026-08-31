FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

# Copy source code and configuration
COPY src/ ./src/
COPY config/ ./config/
COPY main.py .

# Create data directory
RUN mkdir -p /app/data

ENTRYPOINT ["python", "main.py", "--clean-phones"]
CMD ["-f", "config/keywords.txt"]
