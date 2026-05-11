# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rate limiting backed by SQLite.

Two layers:
- Per-IP cooldown — one claim per IP within `ip_cooldown_hours`.
- Daily cap — global count of successful claims per UTC calendar day.

SQLite is plenty fast for the volumes this faucet sees (single-digit thousands
of claims per day at most). WAL mode gives concurrent readers. No external
dependencies, no separate service to run.

We deliberately persist only what's needed for rate-limiting decisions — no
personal data, no claimed-amount details beyond what's necessary.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

log = logging.getLogger(__name__)


# Schema bootstrap is split into three stages so we can layer forward
# migrations cleanly on top of existing databases:
#   1. _BASE_SCHEMA — tables only (no indexes on columns added later)
#   2. _add_column_if_missing — ALTER TABLE for new columns (idempotent)
#   3. _POST_MIGRATE_INDEXES — indexes that may reference newly-added cols
_BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ip              TEXT    NOT NULL,
    created_at      INTEGER NOT NULL,   -- unix seconds (mint time)
    day_utc         TEXT    NOT NULL,   -- YYYY-MM-DD in UTC
    link_id         TEXT,
    amount_sats     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_ip_created ON claims (ip, created_at);
CREATE INDEX IF NOT EXISTS idx_claims_day        ON claims (day_utc);

CREATE TABLE IF NOT EXISTS used_nonces (
    nonce      TEXT    PRIMARY KEY,
    expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nonces_exp ON used_nonces (expires_at);

CREATE TABLE IF NOT EXISTS challenge_hits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ip         TEXT    NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chits_ip_created ON challenge_hits (ip, created_at);
"""

_POST_MIGRATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_claims_redeemed ON claims (redeemed_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_webhook_token
    ON claims (webhook_token) WHERE webhook_token IS NOT NULL;
"""


async def _add_column_if_missing(db: "aiosqlite.Connection", table: str, column_def: str) -> None:
    """Idempotent ALTER TABLE ADD COLUMN for forward migrations.

    SQLite has no `IF NOT EXISTS` for ADD COLUMN, so we peek at PRAGMA
    table_info first. Cheap and safe to run on every boot.
    """
    column_name = column_def.split()[0]
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        cols = {row[1] async for row in cur}
    if column_name not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


@dataclass(slots=True, frozen=True)
class RateLimitVerdict:
    """Outcome of a pre-claim check."""

    allowed: bool
    reason: str | None = None
    retry_after_seconds: int | None = None


@dataclass(slots=True, frozen=True)
class RedeemedClaim:
    """Returned from `mark_redeemed` so callers can fan out webhooks."""

    link_id: str
    amount_sats: int
    minted_at: int      # unix seconds
    redeemed_at: int    # unix seconds


class RateLimiter:
    def __init__(self, db_path: Path, *, ip_cooldown_hours: int, daily_cap: int) -> None:
        self._db_path = db_path
        self._cooldown = ip_cooldown_hours * 3600
        self._daily_cap = daily_cap
        self._initialised = False

    async def init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._conn() as db:
            # Stage 1: base tables + indexes that exist on day-one columns
            await db.executescript(_BASE_SCHEMA)
            # Stage 2: forward migrations (no-op on fresh DBs)
            await _add_column_if_missing(db, "claims", "webhook_token TEXT")
            await _add_column_if_missing(db, "claims", "redeemed_at INTEGER")
            # Stage 3: indexes that reference columns from stage 2
            await db.executescript(_POST_MIGRATE_INDEXES)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.commit()
        self._initialised = True
        log.info("rate limiter ready at %s", self._db_path)

    @asynccontextmanager
    async def _conn(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            yield db

    # ── checks ─────────────────────────────────────────────────────────────

    async def check(self, *, ip: str) -> RateLimitVerdict:
        """Read-only pre-flight: would a claim from `ip` be allowed right now?"""
        now = _now()
        today = _today_utc()
        async with self._conn() as db:
            # Daily cap?
            row = await (await db.execute(
                "SELECT COUNT(*) FROM claims WHERE day_utc = ?", (today,)
            )).fetchone()
            count_today = row[0] if row else 0
            if count_today >= self._daily_cap:
                return RateLimitVerdict(
                    allowed=False,
                    reason="daily_cap_reached",
                    retry_after_seconds=_seconds_until_utc_midnight(),
                )

            # Per-IP cooldown?
            if self._cooldown > 0:
                row = await (await db.execute(
                    "SELECT MAX(created_at) FROM claims WHERE ip = ?", (ip,)
                )).fetchone()
                last = row[0] if row and row[0] is not None else 0
                if last and now - last < self._cooldown:
                    return RateLimitVerdict(
                        allowed=False,
                        reason="ip_cooldown",
                        retry_after_seconds=self._cooldown - (now - last),
                    )

        return RateLimitVerdict(allowed=True)

    async def record(
        self,
        *,
        ip: str,
        link_id: str,
        amount_sats: int,
        webhook_token: str | None = None,
    ) -> None:
        """Persist a successful claim. Call only AFTER LNbits link creation succeeded.

        Pass `webhook_token` if a webhook URL containing that token was given
        to LNbits at link-creation time. The token is the secret that maps an
        incoming LNbits callback back to the originating claim.
        """
        async with self._conn() as db:
            await db.execute(
                "INSERT INTO claims (ip, created_at, day_utc, link_id, amount_sats, webhook_token) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ip, _now(), _today_utc(), link_id, amount_sats, webhook_token),
            )
            await db.commit()

    # ── redemption tracking (called from /api/webhook/lnbits) ─────────────

    async def mark_redeemed(self, *, webhook_token: str, link_id: str) -> "RedeemedClaim | None":
        """Mark a claim as redeemed (sats actually withdrawn by user).

        Returns the matching claim record on success (so the caller can fan
        out forwarding webhooks), or None if:
          - the token doesn't match any claim (spoofed callback), OR
          - the body-claimed link_id doesn't match what we stored, OR
          - the claim was already redeemed (idempotent: double-fire is no-op).
        """
        now = _now()
        async with self._conn() as db:
            async with db.execute(
                "SELECT id, link_id, amount_sats, created_at, redeemed_at "
                "FROM claims WHERE webhook_token = ?",
                (webhook_token,),
            ) as cur:
                row = await cur.fetchone()
            if row is None:
                return None
            claim_id, stored_link_id, amount, created_at, already_redeemed = row
            if stored_link_id != link_id:
                log.warning(
                    "webhook link_id mismatch token=%s stored=%s claimed=%s",
                    webhook_token, stored_link_id, link_id,
                )
                return None
            if already_redeemed is not None:
                return None   # idempotent: webhook already processed
            await db.execute(
                "UPDATE claims SET redeemed_at = ? WHERE id = ?",
                (now, claim_id),
            )
            await db.commit()
        return RedeemedClaim(
            link_id=stored_link_id,
            amount_sats=int(amount),
            minted_at=int(created_at),
            redeemed_at=now,
        )

    # ── PoW nonce single-use tracking ─────────────────────────────────────

    async def consume_nonce(self, nonce: str, expires_at: int) -> bool:
        """Atomically mark `nonce` as used.

        Returns True if this was the first use (claim may proceed), False if
        the nonce was already consumed (replay attempt).

        We also opportunistically prune expired entries so the table doesn't
        grow without bound.
        """
        import aiosqlite as _sql  # local to keep top imports tidy

        async with self._conn() as db:
            try:
                await db.execute(
                    "INSERT INTO used_nonces (nonce, expires_at) VALUES (?, ?)",
                    (nonce, expires_at),
                )
                await db.execute(
                    "DELETE FROM used_nonces WHERE expires_at < ?", (_now(),)
                )
                await db.commit()
                return True
            except _sql.IntegrityError:
                return False

    # ── per-endpoint throttle (used by /api/challenge) ────────────────────

    async def challenge_throttle(
        self,
        *,
        ip: str,
        window_seconds: int,
        max_in_window: int,
    ) -> RateLimitVerdict:
        """Allow at most `max_in_window` challenge requests per IP per window.

        Defends /api/challenge against spam: requesting a fresh token is cheap
        for us but cheaper for an attacker to abuse for bandwidth or warmup.

        Idempotent enough to run on every request — one INSERT + one SELECT.
        """
        now = _now()
        cutoff = now - window_seconds
        async with self._conn() as db:
            row = await (await db.execute(
                "SELECT COUNT(*) FROM challenge_hits WHERE ip = ? AND created_at >= ?",
                (ip, cutoff),
            )).fetchone()
            count = row[0] if row else 0
            if count >= max_in_window:
                return RateLimitVerdict(
                    allowed=False,
                    reason="challenge_throttled",
                    retry_after_seconds=window_seconds,
                )
            await db.execute(
                "INSERT INTO challenge_hits (ip, created_at) VALUES (?, ?)",
                (ip, now),
            )
            # Periodic cleanup: every ~50th insert. Cheap, keeps table small.
            if count % 50 == 0:
                await db.execute(
                    "DELETE FROM challenge_hits WHERE created_at < ?",
                    (now - window_seconds * 4,),
                )
            await db.commit()
        return RateLimitVerdict(allowed=True)

    # ── stats (used by /api/health) ────────────────────────────────────────

    async def stats(self) -> dict[str, int | None]:
        """Aggregate counters used by /api/health.

        We report both **minted** counts (links we created) and **redeemed**
        counts (links the user actually claimed). The gap is the no-show rate.
        """
        today = _today_utc()
        async with self._conn() as db:
            row = await (await db.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_sats), 0) "
                "FROM claims WHERE day_utc = ?",
                (today,),
            )).fetchone()
            today_minted_count, today_minted_sats = (row or (0, 0))

            row = await (await db.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_sats), 0) "
                "FROM claims WHERE day_utc = ? AND redeemed_at IS NOT NULL",
                (today,),
            )).fetchone()
            today_redeemed_count, today_redeemed_sats = (row or (0, 0))

            row = await (await db.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_sats), 0) FROM claims"
            )).fetchone()
            total_minted_count, total_minted_sats = (row or (0, 0))

            row = await (await db.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_sats), 0), MAX(redeemed_at) "
                "FROM claims WHERE redeemed_at IS NOT NULL"
            )).fetchone()
            total_redeemed_count, total_redeemed_sats, last_redemption_at = (
                row or (0, 0, None)
            )

        return {
            "today_count": int(today_minted_count),     # mint-side, kept name for back-compat
            "today_sats": int(today_minted_sats),
            "today_redeemed_count": int(today_redeemed_count),
            "today_redeemed_sats": int(today_redeemed_sats),
            "total_count": int(total_minted_count),
            "total_sats": int(total_minted_sats),
            "total_redeemed_count": int(total_redeemed_count),
            "total_redeemed_sats": int(total_redeemed_sats),
            "last_redemption_at": int(last_redemption_at) if last_redemption_at else None,
            "daily_cap": self._daily_cap,
        }


# ── time helpers ────────────────────────────────────────────────────────────


def _now() -> int:
    return int(datetime.now(UTC).timestamp())


def _today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(UTC)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_tomorrow = start_of_today + timedelta(days=1)
    return int((start_of_tomorrow - now).total_seconds())
