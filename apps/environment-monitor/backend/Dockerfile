FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    i2c-tools \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5001

# Use Gunicorn for production.
# No --max-requests: it was a band-aid for the JSON-era all-data-in-RAM bloat
# (b64c9ad). Post-SQLite there is nothing to recycle away, and every worker
# recycle re-inits the sensor, re-runs the startup backfill and drops the
# sensor thread's buffered write batch.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "1", "--timeout", "300", "--worker-class", "uvicorn.workers.UvicornWorker", "app:app"]
