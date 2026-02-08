FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    curl \
    ffmpeg \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./
# Be more resilient when downloading large wheels (tensorflow, mediapipe).
# Increase timeouts and retries, prefer binary wheels and avoid caching to reduce image size.
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefer-binary --retries 10 --timeout 120 -r requirements.txt

# Copy app
COPY . /app

EXPOSE 5000



# Start Flask app
CMD ["python", "app.py"]