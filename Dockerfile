# ============================================
# RetroIPTVGuide - Dockerfile
# ============================================
FROM python:3.12-slim

LABEL maintainer="thehack904"
LABEL description="RetroIPTVGuide Flask + SQLite Web App"
LABEL version="3.1.0"

# --------------------------------------------
# Environment setup
# --------------------------------------------
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR $APP_HOME

# --------------------------------------------
# Install minimal system dependencies
# --------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini \
        curl \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------
# Copy and install Python dependencies
# --------------------------------------------
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# --------------------------------------------
# Copy application code
# --------------------------------------------
COPY . .

# --------------------------------------------
# Create persistent directories for TrueNAS mounts
# --------------------------------------------
RUN mkdir -p /app/config /app/logs /app/data

# --------------------------------------------
# Expose Flask port
# --------------------------------------------
EXPOSE 5000

# --------------------------------------------
# Use tini as init for graceful shutdown handling
# --------------------------------------------
ENTRYPOINT ["/usr/bin/tini", "--"]

# --------------------------------------------
# Start the Flask app
# (Change app.py to wsgi.py if you ever switch to gunicorn)
# --------------------------------------------
CMD ["python", "app.py"]
