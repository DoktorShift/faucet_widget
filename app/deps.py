# SPDX-License-Identifier: AGPL-3.0-or-later
"""Request-scoped dependencies.

The FastAPI app builds three long-lived services in `lifespan` (config,
LNbits client, anti-bot verifier, rate limiter). These getters expose them to
route handlers via `Depends()`.

Also: client IP extraction. We prefer Cloudflare's `CF-Connecting-IP` header
(since the user runs Cloudflared in front of the service), fall back to
`X-Forwarded-For`'s first hop, and finally to the peer address. This handles
both the Cloudflared setup and direct uvicorn-on-localhost during dev.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.lnbits import LNbitsClient
from app.pow import Antibot
from app.ratelimit import RateLimiter


def get_app_settings() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_lnbits(request: Request) -> LNbitsClient:
    return request.app.state.lnbits  # type: ignore[no-any-return]


def get_antibot(request: Request) -> Antibot:
    return request.app.state.antibot  # type: ignore[no-any-return]


def get_ratelimiter(request: Request) -> RateLimiter:
    return request.app.state.ratelimiter  # type: ignore[no-any-return]


LNbitsDep = Annotated[LNbitsClient, Depends(get_lnbits)]
AntibotDep = Annotated[Antibot, Depends(get_antibot)]
RateLimitDep = Annotated[RateLimiter, Depends(get_ratelimiter)]


def client_ip(request: Request) -> str:
    """Best-effort real-client-IP detection.

    Trust order:
    1. `CF-Connecting-IP` — set by Cloudflare/Cloudflared. The user's setup
       puts Cloudflared in front so this is the most reliable signal.
    2. `X-Forwarded-For` first hop — set by generic reverse proxies.
    3. `request.client.host` — direct connection.

    NOTE: we don't validate which upstream proxy injected these headers. In
    this deployment topology that's fine: the container binds 127.0.0.1, so
    anything that reaches it has already passed Cloudflared. If you ever
    expose this service directly to the internet, validate the proxy first.
    """
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


ClientIPDep = Annotated[str, Depends(client_ip)]
