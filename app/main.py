"""FastAPI app entry point.

Wires:
- Config loading (fail-fast at startup)
- Long-lived services (LNbits client, anti-bot, rate limiter) into app.state
- CORS middleware locked to configured origins
- Static mount of the built frontend
- API routes (/api/challenge, /api/claim, /api/config, /api/health)
- A catch-all route that returns the SPA's index.html (so deep links work)

Logs are structured JSON when stderr isn't a TTY, plain text otherwise. The
container runs in JSON mode by default.
"""

# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app import __version__
from app.config import Settings, get_settings
from app.lnbits import LNbitsClient
from app.pow import Antibot
from app.ratelimit import RateLimiter
from app.routes import claim as claim_routes
from app.routes import meta as meta_routes

# ── logging ────────────────────────────────────────────────────────────────


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Quiet httpx — it logs every request at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)


_configure_logging()
log = logging.getLogger("value4value")


# ── lifecycle ──────────────────────────────────────────────────────────────


DIST_ROOT = Path(__file__).resolve().parent.parent / "dist"
LANDING_DIST = DIST_ROOT / "landing"
EMBED_DIST = DIST_ROOT / "embed"
SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "claims.sqlite"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = get_settings()

    log.info("value4value v%s starting (lnbits.mock=%s)", __version__, settings.lnbits.mock)

    lnbits = LNbitsClient(settings.lnbits)
    antibot = Antibot(settings.antibot)
    ratelimiter = RateLimiter(
        SQLITE_PATH,
        ip_cooldown_hours=settings.claim.ip_cooldown_hours,
        daily_cap=settings.claim.daily_cap,
    )
    await ratelimiter.init()

    app.state.settings = settings
    app.state.lnbits = lnbits
    app.state.antibot = antibot
    app.state.ratelimiter = ratelimiter

    try:
        yield
    finally:
        log.info("value4value shutting down")
        await lnbits.aclose()


# ── app ────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="value4value",
    description="Lightning sats faucet for orange-pilling website visitors.",
    version=__version__,
    lifespan=lifespan,
    # Hide auto-generated docs in production — uncomment for dev if useful.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Settings need to be available before lifespan runs CORS middleware setup, so
# we load them once here too. `get_settings()` is cached.
_settings = get_settings()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds conservative security headers, strips info-leak headers.

    These defaults are safe for the API and the SPA we serve. If you embed
    third-party iframes/scripts in the landing later, relax CSP accordingly.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Strip server-stack identifier. Starlette's MutableHeaders has no
        # `.pop`, so check-then-delete.
        if "server" in response.headers:
            del response.headers["server"]
        # Reasonable defaults
        if "X-Content-Type-Options" not in response.headers:
            response.headers["X-Content-Type-Options"] = "nosniff"
        if "Referrer-Policy" not in response.headers:
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if "X-Frame-Options" not in response.headers:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if "Permissions-Policy" not in response.headers:
            response.headers["Permissions-Policy"] = (
                "camera=(), microphone=(), geolocation=(), payment=()"
            )
        # Only the landing HTML benefits from CSP — applied conservatively so
        # we don't break the inline SVG QR. The embed.js loaded by 3rd-party
        # sites has its own context (the host's CSP), we can't control that.
        if (request.url.path == "/" or request.url.path.endswith(".html")) and \
                "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; "          # Vite-injected styles
                "script-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.app.cors_origins,
    allow_credentials=False,           # we don't use cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)

# API routes
app.include_router(claim_routes.router)
app.include_router(meta_routes.router)


# ── static / SPA ───────────────────────────────────────────────────────────


# Embed widget: served at /embed.js (and embed.js.map for sourcemaps). Mounted
# explicitly because the WP-side snippet links directly to /embed.js.
if EMBED_DIST.exists():
    app.mount("/embed", StaticFiles(directory=EMBED_DIST), name="embed")


@app.get("/embed.js", include_in_schema=False, response_model=None)
async def embed_js() -> FileResponse | JSONResponse:
    """Convenience alias so the WP snippet stays clean: `<script src=".../embed.js">`."""
    target = EMBED_DIST / "embed.js"
    if not target.exists():
        return JSONResponse(
            status_code=503,
            content={"error": "embed widget not built yet. Run `npm run build:embed`."},
        )
    # 5 minute cache — embed is versioned by content hash via Vite anyway.
    return FileResponse(
        target,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


# Landing-page SPA — served at /, /assets/* etc. Falls back to index.html for
# unknown routes so client-side routing works.
if LANDING_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=LANDING_DIST / "assets"),
        name="assets",
    )

    _LANDING_ROOT = LANDING_DIST.resolve()

    @app.get("/", include_in_schema=False, response_model=None)
    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def serve_spa(full_path: str = "") -> FileResponse | JSONResponse:
        index = LANDING_DIST / "index.html"
        if not index.exists():
            return JSONResponse(
                status_code=503,
                content={"error": "landing not built. Run `npm run build`."},
            )

        # If the request matches a real file in dist (e.g. /favicon.ico,
        # /robots.txt), serve that file. Path-traversal guard ensures we
        # only serve files inside LANDING_DIST.
        if full_path:
            candidate = (LANDING_DIST / full_path).resolve()
            try:
                candidate.relative_to(_LANDING_ROOT)
            except ValueError:
                # Path tried to escape; fall through to SPA fallback.
                candidate = None  # type: ignore[assignment]
            if candidate and candidate.is_file():
                return FileResponse(candidate)

        # SPA fallback — short cache because index.html is the bootstrap.
        # Hashed assets are cached aggressively by the /assets mount.
        return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-cache"})
