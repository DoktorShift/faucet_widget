# SPDX-License-Identifier: AGPL-3.0-or-later
"""Non-claim endpoints: health, public config.

`/api/config` exposes the **safe-to-publish** subset of settings the frontend
needs (wallet list, claim amount, language). Keys, secrets, and URLs that
aren't user-facing stay server-side.

`/api/health` is the monitoring endpoint. It is designed to be readable both
by humans (rich JSON) and machines (proper HTTP status codes, predictable
field set). It is the single contract consumed by pull-monitoring tools
(UptimeRobot, Healthchecks.io, k8s readiness probes) AND by our own
background alert monitor.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.deps import LNbitsDep, RateLimitDep, SettingsDep

router = APIRouter(prefix="/api", tags=["meta"])


# ── /api/config ─────────────────────────────────────────────────────────────


class WalletInfo(BaseModel):
    name: str
    tagline: str
    logo: str
    url: str


class PublicConfig(BaseModel):
    amount_sats: int
    default_lang: str
    wallets: list[WalletInfo]
    min_time_on_page_seconds: int


@router.get("/config", response_model=PublicConfig)
async def public_config(settings: SettingsDep) -> PublicConfig:
    return PublicConfig(
        amount_sats=settings.claim.amount_sats,
        default_lang=settings.app.default_lang,
        wallets=[
            WalletInfo(
                name=w.name,
                tagline=w.tagline,
                logo=w.logo,
                url=str(w.url),
            )
            for w in settings.wallets.items
        ],
        min_time_on_page_seconds=settings.antibot.min_time_on_page_seconds,
    )


# ── /api/health ─────────────────────────────────────────────────────────────


HealthStatus = Literal["healthy", "degraded", "low_pot", "pot_empty"]


class HealthBody(BaseModel):
    """Stable contract. Adding new fields is OK; renaming or removing is not."""

    status: HealthStatus = Field(description="Coarse-grained service state")
    ok: bool = Field(description="True when status is healthy or low_pot")

    # Backend reachability
    lnbits_reachable: bool

    # Budget today
    daily_cap: int
    today_count: int       # claims minted today
    today_sats: int        # sats committed today
    remaining_today: int   # daily_cap - today_count
    low_pot_warning: bool  # remaining_today below configured threshold

    # Redemption metrics (None when webhooks not yet active)
    total_minted_count: int
    total_redeemed_count: int
    redemption_rate: float | None = Field(
        description="redeemed/minted, 0.0 to 1.0, null if no mints yet"
    )
    last_redemption_at: int | None = Field(
        description="Unix seconds, or null if no redemption seen yet"
    )


def _compute_status(
    *,
    lnbits_reachable: bool,
    remaining: int,
    low_pot: bool,
) -> HealthStatus:
    if not lnbits_reachable:
        return "degraded"
    if remaining <= 0:
        return "pot_empty"
    if low_pot:
        return "low_pot"
    return "healthy"


@router.get("/health", response_model=HealthBody)
async def health(
    response: Response,
    settings: SettingsDep,
    lnbits: LNbitsDep,
    ratelimiter: RateLimitDep,
) -> HealthBody:
    stats = await ratelimiter.stats()
    lnbits_ok = await lnbits.health()

    daily_cap = settings.claim.daily_cap
    today_count = stats["today_count"] or 0
    remaining = max(0, daily_cap - today_count)

    threshold_count = max(
        1,
        daily_cap * settings.alerts.low_pot_threshold_pct // 100,
    )
    low_pot = remaining > 0 and remaining <= threshold_count

    health_status = _compute_status(
        lnbits_reachable=lnbits_ok,
        remaining=remaining,
        low_pot=low_pot,
    )

    # HTTP status code: 200 for anything we'd still serve from, 503 only
    # when LNbits is unreachable (we genuinely can't fulfil claims).
    # `low_pot` and `pot_empty` are operational signals, not outages —
    # /api/health returns 200 so monitors don't false-alarm at end of day.
    if not lnbits_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    total_minted = stats["total_count"] or 0
    total_redeemed = stats["total_redeemed_count"] or 0
    redemption_rate: float | None = (
        round(total_redeemed / total_minted, 4) if total_minted else None
    )

    return HealthBody(
        status=health_status,
        ok=health_status in ("healthy", "low_pot"),
        lnbits_reachable=lnbits_ok,
        daily_cap=daily_cap,
        today_count=today_count,
        today_sats=stats["today_sats"] or 0,
        remaining_today=remaining,
        low_pot_warning=low_pot,
        total_minted_count=total_minted,
        total_redeemed_count=total_redeemed,
        redemption_rate=redemption_rate,
        last_redemption_at=stats["last_redemption_at"],
    )
