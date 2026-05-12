"""DIY anti-bot: HMAC-signed proof-of-work challenges + honeypot + time-gate.

This replaces a 3rd-party captcha service. It costs an attacker CPU per
attempt (PoW), filters dumb form bots (honeypot field), and rejects
instant-submit bots (min time on page). All stateless on the server — the
challenge itself carries everything we need to verify it.

Flow:
1. Client GETs /api/challenge on page load. The server stamps `issued_at`
   into the signed token; that timestamp is the canonical "user arrived"
   moment used by the time-on-page check.
2. Server creates a challenge: { nonce, difficulty, issued_at, exp }, signs
   it with HMAC-SHA256, returns it as a token.
3. Client solves the PoW: find `solution` such that
   sha256(token + ":" + solution) starts with `difficulty` zero bits.
4. Client POSTs /api/claim with { token, solution, hp }.
5. Server re-verifies HMAC → checks expiry → checks honeypot is empty
   → checks (now - issued_at) >= min_time_on_page → checks PoW.

The signature prevents tampering. The HMAC secret never leaves the server.
Timing is server-authoritative on purpose: a client-supplied "started_at"
would be brittle against clock skew and trivially spoofable.

This is a deliberately small, dependency-free implementation. ~150 lines, no
external lib, easy to audit.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass

from app.config import AntibotSection

# SPDX-License-Identifier: AGPL-3.0-or-later
log = logging.getLogger(__name__)


# A few constants. Keep these small and explicit.
_TOKEN_VERSION = "v1"
_NONCE_BYTES = 16  # 32 hex chars
_SEP = "."


# ─── public API ─────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class Challenge:
    """What the client receives. Encodes everything verifier needs."""

    token: str
    difficulty: int
    expires_at: int


@dataclass(slots=True, frozen=True)
class VerifiedChallenge:
    """Fields extracted from a successfully verified token."""

    nonce: str
    expires_at: int


class AntibotError(ValueError):
    """Raised when verification fails. Message is safe to surface to the user."""


class Antibot:
    """Stateless anti-bot verifier.

    A single instance lives on the FastAPI app state.
    """

    def __init__(self, cfg: AntibotSection) -> None:
        self._cfg = cfg
        self._secret = cfg.hmac_secret.encode()

    @property
    def difficulty(self) -> int:
        return self._cfg.pow_difficulty

    @property
    def min_time_on_page(self) -> int:
        return self._cfg.min_time_on_page_seconds

    # ── issue ──────────────────────────────────────────────────────────────

    def issue(self) -> Challenge:
        """Mint a fresh challenge."""
        nonce = secrets.token_hex(_NONCE_BYTES)
        issued_at = int(time.time())
        exp = issued_at + self._cfg.challenge_ttl_seconds
        token = self._sign(nonce, self._cfg.pow_difficulty, issued_at, exp)
        return Challenge(token=token, difficulty=self._cfg.pow_difficulty, expires_at=exp)

    # ── verify ─────────────────────────────────────────────────────────────

    def verify(
        self,
        *,
        token: str,
        solution: str,
        honeypot: str,
    ) -> VerifiedChallenge:
        """Validate a claim submission.

        Returns a `VerifiedChallenge` with the parsed nonce/expiry on success.
        Raises `AntibotError` if anything is wrong.

        Run checks in a deterministic order so legit clients get helpful
        messages while bots learn as little as possible.

        Time-on-page is measured against the server-signed `issued_at` baked
        into the token. This means the frontend must fetch the challenge on
        page load (not on submit) for `min_time_on_page_seconds` to mean
        what its name says.
        """
        # 1) Honeypot: any non-empty value means it's a bot.
        if honeypot:
            log.info("antibot reject: honeypot filled")
            raise AntibotError("Invalid submission.")

        # 2) Parse + HMAC-verify the token.
        try:
            nonce, difficulty, issued_at, exp = self._verify_signature(token)
        except AntibotError:
            raise
        except Exception as exc:
            log.info("antibot reject: token parse failed: %s", exc)
            raise AntibotError("Invalid or expired challenge.") from None

        # 3) Expiry.
        now = int(time.time())
        if now >= exp:
            log.info("antibot reject: token expired (%ds ago)", now - exp)
            raise AntibotError("Challenge expired. Please try again.")

        # 4) Time-on-page — server-clock vs server-stamped issued_at, so
        #    client clock skew can't push a submission past this check.
        elapsed = now - issued_at
        if elapsed < self._cfg.min_time_on_page_seconds:
            log.info("antibot reject: too fast (%ds)", elapsed)
            raise AntibotError("Slow down — please wait a moment.")

        # 5) Proof-of-work.
        if not self._check_pow(token, solution, difficulty):
            log.info("antibot reject: bad PoW")
            raise AntibotError("Invalid proof-of-work.")

        return VerifiedChallenge(nonce=nonce, expires_at=exp)

    # ── internals ──────────────────────────────────────────────────────────

    def _sign(self, nonce: str, difficulty: int, issued_at: int, exp: int) -> str:
        payload = f"{_TOKEN_VERSION}{_SEP}{nonce}{_SEP}{difficulty}{_SEP}{issued_at}{_SEP}{exp}"
        sig = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}{_SEP}{sig}"

    def _verify_signature(self, token: str) -> tuple[str, int, int, int]:
        parts = token.split(_SEP)
        if len(parts) != 6:
            raise AntibotError("Malformed token.")
        version, nonce, difficulty_s, issued_s, exp_s, sig = parts
        if version != _TOKEN_VERSION:
            raise AntibotError("Unsupported challenge version.")
        payload = _SEP.join(parts[:-1])
        expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise AntibotError("Invalid signature.")
        return nonce, int(difficulty_s), int(issued_s), int(exp_s)

    @staticmethod
    def _check_pow(token: str, solution: str, difficulty: int) -> bool:
        """Verify SHA-256(token + ':' + solution) has `difficulty` leading
        zero bits."""
        if not solution or len(solution) > 64:
            return False
        digest = hashlib.sha256(f"{token}:{solution}".encode()).digest()
        return _leading_zero_bits(digest) >= difficulty


def _leading_zero_bits(data: bytes) -> int:
    """Count leading zero bits in a byte string."""
    count = 0
    for byte in data:
        if byte == 0:
            count += 8
            continue
        # Count remaining leading zeros in this byte
        mask = 0x80
        while mask and not (byte & mask):
            count += 1
            mask >>= 1
        break
    return count
