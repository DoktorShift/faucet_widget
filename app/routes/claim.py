"""Claim flow — the heart of the service.

Two endpoints:

GET /api/challenge
    Issue a fresh anti-bot challenge. Cheap, idempotent, never touches LNbits.
    The client uses the returned token + difficulty to solve the PoW locally.

POST /api/claim
    Verify the challenge, then verify rate limits, then create an LNbits
    withdraw link. Returns the LNURL, the `lightning:` URI, and an SVG QR.

Both endpoints are JSON, both are CORS-restricted via the app-level
middleware in main.py.

Error handling philosophy: surface user-correctable errors verbatim (expired
challenge, rate-limited) with the right HTTP status. For internal errors
(LNbits unreachable, DB write fails) we log the detail and return a generic
500 so we don't leak internals.
"""

# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import (
    AntibotDep,
    ClientIPDep,
    LNbitsDep,
    RateLimitDep,
    SettingsDep,
)
from app.lnbits import LNbitsError
from app.pow import AntibotError
from app.qr import make_qr_svg

# Per-IP throttle on /api/challenge: 30 fresh challenges per minute per IP.
# Way more than any human needs; absorbs accidental retries during PoW solve.
_CHALLENGE_WINDOW_SECONDS = 60
_CHALLENGE_MAX_PER_WINDOW = 30

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["claim"])


# ── schemas ─────────────────────────────────────────────────────────────────


class ChallengeResponse(BaseModel):
    token: str
    difficulty: int = Field(description="Number of leading zero bits the solution must satisfy")
    expires_at: int = Field(description="Unix timestamp (seconds) after which the token is invalid")
    min_time_on_page_seconds: int


class ClaimRequest(BaseModel):
    token: str
    solution: str
    started_at: int = Field(
        description="Client unix-seconds timestamp when the page first rendered",
    )
    # Honeypot field — must remain empty. Real clients leave it untouched;
    # bots that auto-fill form inputs will fill it.
    hp: str = ""


class ClaimResponse(BaseModel):
    link_id: str
    lnurl: str
    lightning_uri: str
    amount_sats: int
    qr_svg: str


# ── /api/challenge ──────────────────────────────────────────────────────────


@router.get("/challenge", response_model=ChallengeResponse)
async def issue_challenge(
    antibot: AntibotDep,
    ratelimiter: RateLimitDep,
    ip: ClientIPDep,
) -> ChallengeResponse:
    # Per-IP throttle so an attacker can't spam challenge tokens cheaply.
    verdict = await ratelimiter.challenge_throttle(
        ip=ip,
        window_seconds=_CHALLENGE_WINDOW_SECONDS,
        max_in_window=_CHALLENGE_MAX_PER_WINDOW,
    )
    if not verdict.allowed:
        headers = {}
        if verdict.retry_after_seconds is not None:
            headers["Retry-After"] = str(verdict.retry_after_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Slow down.",
            headers=headers,
        )

    ch = antibot.issue()
    return ChallengeResponse(
        token=ch.token,
        difficulty=ch.difficulty,
        expires_at=ch.expires_at,
        min_time_on_page_seconds=antibot.min_time_on_page,
    )


# ── /api/claim ──────────────────────────────────────────────────────────────


@router.post("/claim", response_model=ClaimResponse)
async def claim(
    body: ClaimRequest,
    settings: SettingsDep,
    antibot: AntibotDep,
    lnbits: LNbitsDep,
    ratelimiter: RateLimitDep,
    ip: ClientIPDep,
) -> ClaimResponse:
    # 1) Anti-bot — fail fast, cheap. Returns the parsed nonce/exp on success.
    try:
        verified = antibot.verify(
            token=body.token,
            solution=body.solution,
            honeypot=body.hp,
            started_at=body.started_at,
        )
    except AntibotError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # 2) Nonce-replay guard — a verified PoW solution may only be used once.
    #    Prevents an attacker who solved one PoW from spending the daily cap
    #    by replaying the same solution from many IPs.
    consumed = await ratelimiter.consume_nonce(verified.nonce, verified.expires_at)
    if not consumed:
        log.info("antibot reject: nonce replayed ip=%s", ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired challenge.",
        )

    # 3) Rate-limit — also cheap, only a couple of indexed queries.
    verdict = await ratelimiter.check(ip=ip)
    if not verdict.allowed:
        msg = _ratelimit_message(verdict.reason)
        headers = {}
        if verdict.retry_after_seconds is not None:
            headers["Retry-After"] = str(verdict.retry_after_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=msg,
            headers=headers,
        )

    # 4) Create the LNbits withdraw link. The title is what the user's wallet
    #    displays when they scan the QR — surface the source site there.
    try:
        link = await lnbits.create_single_use_link(
            amount_sats=settings.claim.amount_sats,
            title=settings.claim.format_title(),
            wait_time_seconds=settings.claim.lnbits_wait_time_seconds,
        )
    except LNbitsError as exc:
        log.exception("LNbits link creation failed for ip=%s", ip)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lightning backend unavailable. Please try again shortly.",
        ) from exc

    # 5) Record the claim — only after LNbits succeeded.
    try:
        await ratelimiter.record(ip=ip, link_id=link.id, amount_sats=link.amount_sats)
    except Exception:
        # Don't punish the user if our local bookkeeping fails — the link is
        # already minted and they have a right to claim. Log and move on.
        log.exception("Failed to record claim for ip=%s link=%s", ip, link.id)

    return ClaimResponse(
        link_id=link.id,
        lnurl=link.lnurl,
        lightning_uri=link.lightning_uri,
        amount_sats=link.amount_sats,
        qr_svg=make_qr_svg(link.lnurl),
    )


# ── helpers ────────────────────────────────────────────────────────────────


def _ratelimit_message(reason: str | None) -> str:
    if reason == "daily_cap_reached":
        return "Today's faucet pot is empty. Please come back tomorrow."
    if reason == "ip_cooldown":
        return "You already claimed recently. Please try again later."
    return "Too many requests."
