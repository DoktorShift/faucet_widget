# SPDX-License-Identifier: AGPL-3.0-or-later
"""LNbits Withdraw-extension client.

We use the Withdraw extension to issue **single-use LNURL-withdraw links**, one
per successful claim. Each link is:
- locked to exactly `amount_sats` (min == max)
- redeemable exactly once (uses == 1)
- short-lived (configurable via claim.link_expiry_seconds, enforced by the
  rate limiter on our side; LNbits itself has no built-in expiry)

A mock mode is provided so the rest of the stack can run without a real LNbits
server (useful for local dev or CI). The mock generates plausible LNURL strings
without hitting the network.

LNbits API reference (Withdraw extension):
    POST /withdraw/api/v1/links            ← create
    GET  /withdraw/api/v1/links/{link_id}  ← read
    DELETE /withdraw/api/v1/links/{link_id}

The created link object includes both `id` and `lnurl` — the latter is the
bech32 LNURL string the user scans.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import LNbitsSection

log = logging.getLogger(__name__)


class LNbitsError(RuntimeError):
    """Raised when LNbits returns a non-2xx response or unreachable."""

    def __init__(self, message: str, *, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass(slots=True, frozen=True)
class WithdrawLink:
    """Result of creating a withdraw link."""

    id: str
    lnurl: str
    amount_sats: int
    uses: int

    @property
    def lightning_uri(self) -> str:
        """`lightning:` URI for wallet deep-link buttons."""
        return f"lightning:{self.lnurl.lower()}"


class LNbitsClient:
    """Thin async client for the LNbits Withdraw extension.

    A single instance is held by the FastAPI app and reused across requests.
    Pooling and keep-alive are handled by the underlying `httpx.AsyncClient`.
    """

    def __init__(self, cfg: LNbitsSection, *, timeout: float = 10.0) -> None:
        self._cfg = cfg
        self._mock = cfg.mock
        if self._mock:
            self._http: httpx.AsyncClient | None = None
            log.warning("LNbits client started in MOCK mode — no real Lightning calls")
            return

        self._http = httpx.AsyncClient(
            base_url=str(cfg.url).rstrip("/"),
            headers={"X-Api-Key": cfg.admin_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()

    # ── public API ───────────────────────────────────────────────────────

    async def create_single_use_link(
        self,
        *,
        amount_sats: int,
        title: str,
        wait_time_seconds: int = 1,
    ) -> WithdrawLink:
        """Create a one-shot LNURL-withdraw link.

        UNIT NOTE: LNbits core stores balances in msats, but the **Withdraw
        extension API** takes `min_withdrawable` / `max_withdrawable` in
        **SATS**. It then multiplies by 1000 internally before returning
        msats in the LNURL-withdraw response (per spec). Verified
        empirically against demo.lnbits.com:

            POST {min_withdrawable: 21}  →  LNURL response minWithdrawable=21000 msat (=21 sat) ✓
            POST {min_withdrawable: 21000} → LNURL response minWithdrawable=21000000 msat (=21000 sat) ✗

        Raises:
            LNbitsError: on network failure or non-2xx response.
        """
        if self._mock:
            return self._mock_link(amount_sats)

        payload = {
            "title": title,
            "min_withdrawable": amount_sats,   # Withdraw extension API is in SATS
            "max_withdrawable": amount_sats,
            "uses": 1,
            "wait_time": max(wait_time_seconds, 1),
            "is_unique": False,
        }
        return await self._post_link(payload, amount_sats)

    async def delete_link(self, link_id: str) -> None:
        """Best-effort cleanup. Errors are logged, not raised — caller doesn't
        need this to block their response."""
        if self._mock or self._http is None:
            return
        try:
            resp = await self._http.delete(f"/withdraw/api/v1/links/{link_id}")
            if resp.status_code >= 400:
                log.warning("LNbits delete link %s returned %s", link_id, resp.status_code)
        except httpx.HTTPError as exc:
            log.warning("LNbits delete link %s failed: %s", link_id, exc)

    async def health(self) -> bool:
        """Lightweight reachability check used by /api/health."""
        if self._mock:
            return True
        if self._http is None:
            return False
        try:
            resp = await self._http.get("/withdraw/api/v1/links", params={"limit": 1})
        except httpx.HTTPError:
            return False
        return resp.status_code < 500

    # ── internals ────────────────────────────────────────────────────────

    async def _post_link(self, payload: dict, amount_sats: int) -> WithdrawLink:
        assert self._http is not None  # nosec - guarded by self._mock branch above
        try:
            resp = await self._http.post("/withdraw/api/v1/links", json=payload)
        except httpx.HTTPError as exc:
            raise LNbitsError(f"LNbits unreachable: {exc}") from exc

        if resp.status_code >= 400:
            raise LNbitsError(
                f"LNbits returned {resp.status_code} on link create",
                status=resp.status_code,
                body=_safe_body(resp),
            )

        body = resp.json()
        link_id = body.get("id")
        lnurl = body.get("lnurl")
        if not link_id or not lnurl:
            raise LNbitsError(
                "LNbits link create succeeded but response missing id/lnurl",
                status=resp.status_code,
                body=body,
            )
        return WithdrawLink(
            id=str(link_id),
            lnurl=str(lnurl),
            amount_sats=amount_sats,
            uses=int(body.get("uses", 1)),
        )

    def _mock_link(self, amount_sats: int) -> WithdrawLink:
        # Produce a string that *looks* like an LNURL so frontends render it.
        # NOT a real LNURL — encoded with garbage so anyone scanning it gets a
        # wallet error, not a real payment attempt.
        fake_id = uuid.uuid4().hex
        fake_lnurl = "LNURL1" + secrets.token_hex(40).upper()
        log.info("MOCK LNbits link created id=%s amount=%s sats", fake_id, amount_sats)
        return WithdrawLink(
            id=fake_id,
            lnurl=fake_lnurl,
            amount_sats=amount_sats,
            uses=1,
        )


def _safe_body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text[:500]
