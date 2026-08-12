# ---------------------------------------------------------------------------
# Single-service image: builds the React app and serves it (plus the API and
# the TensorFlow model) through Flask/Gunicorn on ONE port.
# Tuned for Hugging Face Spaces (Docker SDK): runs as UID 1000, listens on 7860.
# ---------------------------------------------------------------------------

# 1) Build the React production bundle.
#    No frontend/.env is copied, so REACT_APP_BACKEND_URL stays unset and the
#    app calls its own origin (window.location.origin) — i.e. the same URL.
FROM node:18 AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

# 2) Python backend that serves everything.
FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl ffmpeg ca-certificates \
    libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run the container as a non-root user with UID 1000.
RUN useradd -m -u 1000 user

# Python dependencies (installed as root, available to all users).
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary --retries 10 --timeout 120 -r /tmp/requirements.txt

WORKDIR /home/user/app

# Backend code + model artifacts (owned by the runtime user).
COPY --chown=user:user backend/ /home/user/app/

# Built React app -> Flask serves it from here.
COPY --from=frontend-build --chown=user:user /app/build /home/user/app/static

# Writable folder for the SQLite database file.
RUN mkdir -p /home/user/app/data && chown -R user:user /home/user/app

ENV FRONTEND_BUILD_DIR=/home/user/app/static
# Self-contained SQLite DB (no external database needed). Override with a real
# DATABASE_URL env var / secret to use MySQL instead.
ENV DATABASE_URL=sqlite:////home/user/app/data/gesture.db
ENV PORT=7860

USER user
EXPOSE 7860

# Single Gunicorn worker: the TensorFlow model is heavy; multiple workers would
# each load a copy and exhaust memory. $PORT lets other PaaS override the port.
CMD gunicorn --workers 1 --timeout 300 --bind 0.0.0.0:${PORT:-7860} app:app
