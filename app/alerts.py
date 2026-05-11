# SPDX-License-Identifier: AGPL-3.0-or-later
"""Background health monitor that pushes alerts to user webhooks.

Pull-based monitoring (UptimeRobot, Healthchecks.io, k8s readiness) consumes
`/api/health`. This module is the push counterpart: an asyncio task started
in the FastAPI lifespan that snapshots the same data periodically and POSTs
to `alerts.on_health_change` URLs **only** when the coarse-grained state
transitions. Idle steady-state means no traffic.

State transitions we fire on:
    healthy   ↔ degraded   (LNbits up/down)
    healthy   ↔ low_pot    (crossed the threshold)
    low_pot   ↔ pot_empty  (daily_cap hit / new UTC day)
    pot_empty ↔ healthy    (new day reset)

Payloads are Slack/Discord incoming-webhook compatible (a top-level `text`
field) AND include structured `data` for generic consumers (Zapier, n8n,
custom endpoints). Each target webhook is dispatched concurrently and
isolated: one failing webhook never delays or breaks another.

The monitor runs at most one cycle at a time. If a cycle takes longer than
the poll interval (slow LNbits), the next tick simply waits.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

import httpx

from app.config import AlertsSection, Settings
from app.lnbits import LNbitsClient
from app.ratelimit import RateLimiter

log = logging.getLogger(__name__)


HealthStatus = Literal["healthy", "degraded", "low_pot", "pot_empty"]


# Human-readable text for each state transition (Slack/Discord preview).
_TRANSITION_TEXT = {
    "healthy":   ":white_check_mark: faucet healthy: pot replenished, LNbits reachable",
    "degraded":  ":x: faucet DEGRADED: LNbits unreachable",
    "low_pot":   ":warning: faucet low pot: less than {remaining}/{cap} claims left today",
    "pot_empty": ":no_entry: faucet pot EMPTY: daily cap of {cap} claims hit",
}


class AlertMonitor:
    """Long-running background task. Start once in `lifespan`, cancel on shutdown."""

    def __init__(
        self,
        *,
        settings: Settings,
        lnbits: LNbitsClient,
        ratelimiter: RateLimiter,
    ) -> None:
        self._settings = settings
        self._cfg: AlertsSection = settings.alerts
        self._lnbits = lnbits
        self._ratelimiter = ratelimiter
        self._task: asyncio.Task | None = None
        self._last_state: HealthStatus | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._cfg.on_health_change)

    async def start(self) -> None:
        if not self.enabled:
            log.info("alert monitor disabled (no [alerts] webhooks configured)")
            return
        log.info(
            "alert monitor starting (poll=%ds, %d webhook target(s))",
            self._cfg.poll_interval_seconds,
            len(self._cfg.on_health_change),
        )
        self._task = asyncio.create_task(self._run(), name="v4v-alert-monitor")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    # ── internals ──────────────────────────────────────────────────────────

    async def _run(self) -> None:
        # First tick is delayed so the rest of the app finishes coming up
        # before we start hammering health checks.
        await asyncio.sleep(self._cfg.poll_interval_seconds)
        while True:
            try:
                await self._tick()
            except Exception:
                # Never let one failed tick kill the loop.
                log.exception("alert monitor tick failed; continuing")
            await asyncio.sleep(self._cfg.poll_interval_seconds)

    async def _tick(self) -> None:
        state, ctx = await self._snapshot()
        if self._last_state is None:
            # First observation: don't fire an alert, just record.
            self._last_state = state
            log.debug("alert monitor: initial state=%s", state)
            return
        if state == self._last_state:
            return
        log.info("alert monitor: %s -> %s", self._last_state, state)
        prev = self._last_state
        self._last_state = state
        await self._broadcast(state, prev, ctx)

    async def _snapshot(self) -> tuple[HealthStatus, dict]:
        stats = await self._ratelimiter.stats()
        lnbits_ok = await self._lnbits.health()
        cap = self._settings.claim.daily_cap
        today = stats["today_count"] or 0
        remaining = max(0, cap - today)
        threshold = max(1, cap * self._cfg.low_pot_threshold_pct // 100)
        low = remaining > 0 and remaining <= threshold

        if not lnbits_ok:
            state: HealthStatus = "degraded"
        elif remaining <= 0:
            state = "pot_empty"
        elif low:
            state = "low_pot"
        else:
            state = "healthy"

        return state, {
            "cap": cap,
            "today": today,
            "remaining": remaining,
            "lnbits_reachable": lnbits_ok,
        }

    async def _broadcast(
        self,
        state: HealthStatus,
        previous: HealthStatus,
        ctx: dict,
    ) -> None:
        text = _TRANSITION_TEXT[state].format(**ctx)
        payload = {
            "text": text,
            "event": "health_change",
            "data": {
                "from": previous,
                "to": state,
                "lnbits_reachable": ctx["lnbits_reachable"],
                "today_count": ctx["today"],
                "remaining_today": ctx["remaining"],
                "daily_cap": ctx["cap"],
            },
        }
        targets = [str(u) for u in self._cfg.on_health_change]
        async with httpx.AsyncClient(timeout=self._cfg.timeout_seconds) as client:
            results = await asyncio.gather(
                *(_safe_post(client, url, payload) for url in targets),
                return_exceptions=True,
            )
        for url, result in zip(targets, results, strict=True):
            if isinstance(result, Exception):
                log.warning("alert webhook failed %s: %s", url, result)


async def _safe_post(client: httpx.AsyncClient, url: str, payload: dict) -> None:
    resp = await client.post(url, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"{url} returned HTTP {resp.status_code}")
