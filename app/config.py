# SPDX-License-Identifier: AGPL-3.0-or-later
"""Configuration loader.

Reads `config.toml` (path overridable via `V4V_CONFIG` env var) and exposes a
single typed `Settings` object. The TOML layout is documented in
`config.toml.example`.

Design choices:
- Pure Pydantic v2 models, no env-var fallbacks for individual fields. The TOML
  file is the single source of truth. This makes diffs reviewable and prevents
  accidental config drift between dev and prod.
- A few sanity checks fail loudly at startup rather than on first request.
"""

from __future__ import annotations

import os
import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl, field_validator

DEFAULT_CONFIG_PATH = Path("config.toml")


class AppSection(BaseModel):
    base_url: HttpUrl
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=list)
    default_lang: str = Field(default="de", pattern=r"^(de|en)$")


class LNbitsSection(BaseModel):
    mock: bool = False
    url: HttpUrl = Field(default="https://lnbits.eu")  # type: ignore[assignment]
    wallet_id: str
    admin_key: str

    @field_validator("admin_key", "wallet_id")
    @classmethod
    def _placeholder_only_allowed_in_mock(cls, value: str) -> str:
        if value == "REPLACE_ME":
            return value
        return value


class ClaimSection(BaseModel):
    amount_sats: Annotated[int, Field(ge=1, le=1_000_000)] = 21
    daily_cap: Annotated[int, Field(ge=1)] = 100
    ip_cooldown_hours: Annotated[int, Field(ge=0)] = 24
    link_expiry_seconds: Annotated[int, Field(ge=60)] = 3600
    lnbits_wait_time_seconds: Annotated[int, Field(ge=0)] = 1

    # Title passed to LNbits when creating a withdraw link. This is what the
    # user's WALLET displays when they scan the QR. Use it to surface the
    # source site so users know where the gift came from. `{amount}` and
    # `{sats}` placeholders are interpolated at claim time.
    link_title: str = "21m.art · {amount} sats gift"

    # NOTE: do not add an `amount_msats` helper here. The LNbits Withdraw
    # extension API takes SATS, not msats — see app/lnbits.py for details.

    def format_title(self) -> str:
        return self.link_title.format(amount=self.amount_sats, sats=self.amount_sats)


class AntibotSection(BaseModel):
    hmac_secret: str
    pow_difficulty: Annotated[int, Field(ge=8, le=28)] = 18
    challenge_ttl_seconds: Annotated[int, Field(ge=30)] = 300
    min_time_on_page_seconds: Annotated[int, Field(ge=0)] = 2

    @field_validator("hmac_secret")
    @classmethod
    def _no_placeholder(cls, value: str) -> str:
        if value in {"REPLACE_ME", "REPLACE_ME_WITH_32_BYTE_HEX", ""}:
            msg = "antibot.hmac_secret must be set to a random secret"
            raise ValueError(msg)
        if len(value) < 32:
            msg = "antibot.hmac_secret should be at least 32 characters"
            raise ValueError(msg)
        return value


class WalletEntry(BaseModel):
    name: str
    tagline: str = ""
    logo: str = ""
    url: HttpUrl


class WalletsSection(BaseModel):
    # Field is named `items` in code, but the TOML uses `[[wallets.list]]` for
    # readability. The alias maps one to the other. (We avoid naming the field
    # `list` because that shadows the builtin in the class body's annotation
    # scope, which trips Pydantic v2 on Python 3.14.)
    items: list[WalletEntry] = Field(default_factory=list, alias="list")

    model_config = {"populate_by_name": True}


class Settings(BaseModel):
    app: AppSection
    lnbits: LNbitsSection
    claim: ClaimSection
    antibot: AntibotSection
    wallets: WalletsSection

    @field_validator("lnbits")
    @classmethod
    def _real_keys_unless_mock(cls, value: LNbitsSection) -> LNbitsSection:
        if not value.mock and (
            value.admin_key == "REPLACE_ME" or value.wallet_id == "REPLACE_ME"
        ):
            msg = (
                "lnbits.admin_key and lnbits.wallet_id must be set "
                "when lnbits.mock = false"
            )
            raise ValueError(msg)
        return value


def _resolve_config_path() -> Path:
    raw = os.environ.get("V4V_CONFIG")
    return Path(raw).expanduser() if raw else DEFAULT_CONFIG_PATH


def _load_toml(path: Path) -> dict:
    if not path.exists():
        msg = (
            f"Config file not found: {path}.\n"
            "Copy config.toml.example to config.toml and edit it, "
            "or set V4V_CONFIG to a different path."
        )
        raise FileNotFoundError(msg)
    with path.open("rb") as fp:
        return tomllib.load(fp)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — settings are loaded once at first call."""
    path = _resolve_config_path()
    try:
        data = _load_toml(path)
        return Settings.model_validate(data)
    except Exception as exc:
        # Fail loudly with a clear message rather than a Pydantic stacktrace.
        print(f"\n[value4value] FATAL: invalid config ({path}):\n  {exc}\n", file=sys.stderr)
        raise


__all__ = [
    "AntibotSection",
    "AppSection",
    "ClaimSection",
    "LNbitsSection",
    "Settings",
    "WalletEntry",
    "WalletsSection",
    "get_settings",
]
