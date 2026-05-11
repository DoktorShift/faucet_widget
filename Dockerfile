# syntax=docker/dockerfile:1.7

# ─── Stage 1: build frontend ───────────────────────────────────────────────
FROM node:20-alpine AS web-build
WORKDIR /build

# Cache npm install
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# Build both landing (Vue+Tailwind) and embed (vanilla)
COPY vite.config.js vite.embed.config.js tailwind.config.js postcss.config.js ./
COPY web/ ./web/
RUN npm run build


# ─── Stage 2: python runtime ───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Don't run as root inside the container
RUN groupadd --system --gid 1001 v4v && \
    useradd --system --uid 1001 --gid v4v --create-home v4v

WORKDIR /app

# Install Python deps first (better layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Application code + built frontend
COPY app/ ./app/
COPY --from=web-build /build/dist ./dist

# Runtime data lives in a volume
RUN mkdir -p /app/data && chown -R v4v:v4v /app
VOLUME ["/app/data"]

USER v4v

EXPOSE 8000
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*", \
     "--no-server-header", "--no-date-header"]
