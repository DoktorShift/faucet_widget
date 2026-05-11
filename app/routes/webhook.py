# SPDX-License-Identifier: AGPL-3.0-or-later
"""LNbits webhook receiver.

LNbits POSTs to `POST /api/webhook/lnbits/{token}` immediately after a
withdraw link is actually paid out. We:

1. Look up `{token}` in our `claims` table.
2. Verify the body's `lnurlw` (= LNbits link id) matches what we stored.
3. Idempotently mark the claim as redeemed.
4. Fire user-configured forwarding webhooks (best-effort, fan-out).

If any of (1) or (2) fail we respond with **404** so neither a curious
script nor a misrouted retry can probe the endpoint shape. A successful
double-fire (e.g. LNbits retry, though it doesn't retry today) returns
**200** because the operation is idempotent.

Why the token-in-URL pattern?
- LNbits has no built-in webhook signing.
- The token is 16 random bytes generated server-side per claim and stored
  in the same row, so the URL is unguessable without DB access.
- Body verification (`lnurlw` matches) is a second layer.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.deps import RateLimitDep, SettingsDep
from app.ratelimit import RedeemedClaim

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


class LNbitsWebhookBody(BaseModel):
    """Subset of the LNbits Withdraw webhook payload we care about.

    The extension POSTs:
        {
          "payment_hash":    "<hex>",
          "payment_request": "<bolt11>",
          "lnurlw":          "<link_id>",
          "body":            <our custom passthrough or "">
        }

    We accept extra fields without complaining (Pydantic ignores unknowns
    by default).
    """

    lnurlw: str = Field(..., min_length=1, max_length=128)
    payment_hash: str | None = None
    payment_request: str | None = None


@router.post(
    "/lnbits/{token}",
    status_code=status.HTTP_200_OK,
    summary="LNbits Withdraw extension callback (internal)",
    response_model=None,
    include_in_schema=False,
)
async def lnbits_redemption(
    token: str,
    body: LNbitsWebhookBody,
    settings: SettingsDep,
    ratelimiter: RateLimitDep,
    request: Request,
) -> dict[str, str]:
    # 1) + 2) verify token + body link_id match a real claim, mark redeemed
    claim = await ratelimiter.mark_redeemed(webhook_token=token, link_id=body.lnurlw)
    if claim is None:
        # Could be: spoofed call, wrong link_id, or already-redeemed. We treat
        # all three the same way externally so we don't leak which case it is.
        log.info("redemption webhook rejected (token=%s…)", token[:6])
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown claim")

    log.info(
        "claim redeemed link_id=%s amount=%d sats (mint→redeem %ds)",
        claim.link_id,
        claim.amount_sats,
        claim.redeemed_at - claim.minted_at,
    )

    # 3) fan-out forwarding webhooks (don't make LNbits wait on us)
    targets = settings.webhooks.on_claim_redeemed
    if targets:
        # fire-and-forget; the route returns 200 quickly to LNbits
        asyncio.create_task(
            _forward_redemption(
                claim,
                [str(u) for u in targets],
                settings.webhooks.timeout_seconds,
            )
        )

    return {"status": "ok"}


# ── outbound fan-out ────────────────────────────────────────────────────────


async def _forward_redemption(
    claim: RedeemedClaim,
    targets: list[str],
    timeout: float,
) -> None:
    """POST a structured payload to each configured webhook URL.

    Payload is Slack/Discord-incoming-webhook compatible (a `text` field)
    AND includes structured `data` for programmatic consumers.
    """
    sats = claim.amount_sats
    payload = {
        # Slack/Discord show this when posting to their incoming webhooks
        "text": (
            f":zap: faucet redeemed: {sats} sats claimed "
            f"(link `{claim.link_id}`, {claim.redeemed_at - claim.minted_at}s after mint)"
        ),
        # Structured form for Zapier/Make/n8n/custom consumers
        "event": "claim_redeemed",
        "data": {
            "link_id": claim.link_id,
            "amount_sats": sats,
            "minted_at": claim.minted_at,
            "redeemed_at": claim.redeemed_at,
            "time_to_redeem_seconds": claim.redeemed_at - claim.minted_at,
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        # We dispatch all targets concurrently; one slow webhook won't block
        # the others. Failures are logged, never raised; the redemption
        # itself already succeeded.
        results = await asyncio.gather(
            *(_post_one(client, url, payload) for url in targets),
            return_exceptions=True,
        )
    for url, result in zip(targets, results, strict=True):
        if isinstance(result, Exception):
            log.warning("forward webhook failed %s: %s", url, result)


async def _post_one(client: httpx.AsyncClient, url: str, payload: dict) -> None:
    resp = await client.post(url, json=payload)
    if resp.status_code >= 400:
        log.warning("forward webhook %s returned %s", url, resp.status_code)
