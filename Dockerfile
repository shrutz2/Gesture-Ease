FROM node:18 AS frontend-build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

# Backend with static frontend
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl ffmpeg ca-certificates \
    libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary --retries 10 --timeout 120 -r requirements.txt

COPY backend/ /app/

# Copy frontend build to backend static folder
RUN mkdir -p /app/static
COPY --from=frontend-build /app/build /app/static

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
