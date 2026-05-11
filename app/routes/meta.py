# SPDX-License-Identifier: AGPL-3.0-or-later
"""Non-claim endpoints: health, public config.

`/api/config` exposes the **safe-to-publish** subset of settings the frontend
needs (wallet list, claim amount, language). Keys, secrets, and URLs that
aren't user-facing stay server-side.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.deps import LNbitsDep, RateLimitDep, SettingsDep

router = APIRouter(prefix="/api", tags=["meta"])


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


class HealthStatus(BaseModel):
    ok: bool
    lnbits_reachable: bool
    today_count: int = Field(description="Successful claims today")
    today_sats: int
    daily_cap: int


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


@router.get("/health", response_model=HealthStatus)
async def health(
    settings: SettingsDep,
    lnbits: LNbitsDep,
    ratelimiter: RateLimitDep,
) -> HealthStatus:
    stats = await ratelimiter.stats()
    return HealthStatus(
        ok=True,
        lnbits_reachable=await lnbits.health(),
        today_count=stats["today_count"],
        today_sats=stats["today_sats"],
        daily_cap=settings.claim.daily_cap,
    )
