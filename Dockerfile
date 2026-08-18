# Single image: builds the React app and serves it + the API + the model via Flask.

# build the React bundle (no .env copied, so it calls its own origin)
FROM node:18 AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl ffmpeg ca-certificates \
    libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary --retries 10 --timeout 120 -r /tmp/requirements.txt

WORKDIR /home/user/app
COPY --chown=user:user backend/ /home/user/app/
COPY --from=frontend-build --chown=user:user /app/build /home/user/app/static
RUN mkdir -p /home/user/app/data && chown -R user:user /home/user/app

ENV FRONTEND_BUILD_DIR=/home/user/app/static
ENV DATABASE_URL=sqlite:////home/user/app/data/gesture.db
ENV PORT=7860

USER user
EXPOSE 7860

# one worker - the model is heavy; $PORT lets the host override the port
CMD gunicorn --workers 1 --timeout 300 --bind 0.0.0.0:${PORT:-7860} app:app
