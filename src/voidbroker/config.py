"""Runtime configuration, loaded from environment / .env with safe defaults."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLATFORMS = {"pc", "ps4", "xbox", "switch", "mobile"}

# warframe.market exposes two API generations. v2 is current for catalog/orders;
# statistics still lives on v1. We talk to both.
WFM_V1_BASE = "https://api.warframe.market/v1"
WFM_V2_BASE = "https://api.warframe.market/v2"


class Settings(BaseSettings):
    """Application settings. Override any field via VOIDBROKER_<NAME> env vars."""

    model_config = SettingsConfigDict(
        env_prefix="VOIDBROKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    platform: str = "pc"  # pc | ps4 | xbox | switch | mobile
    language: str = "en"  # one of 14 supported codes (en, ru, de, fr, es, ja, ko, ...)
    crossplay: bool = False  # include cross-play orders from other platforms
    db_path: Path = Path("data/voidbroker.duckdb")
    rate_limit: float = Field(default=3.0, gt=0, description="Requests/second cap.")
    request_timeout: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    wfm_token: SecretStr | None = None  # kept secret so it never leaks into logs/reprs

    @field_validator("platform")
    @classmethod
    def _validate_platform(cls, v: str) -> str:
        # platform flows into outbound URL path segments + headers; constrain it to the
        # known values so a stray env var can't produce a malformed/redirected request.
        if v not in _PLATFORMS:
            raise ValueError(f"platform must be one of {sorted(_PLATFORMS)}")
        return v

    @property
    def auth_header(self) -> dict[str, str]:
        # v2 uses OAuth2 Bearer tokens. (Legacy v1 tokens used the "JWT " prefix.)
        if not self.wfm_token:
            return {}
        return {"Authorization": f"Bearer {self.wfm_token.get_secret_value()}"}


def get_settings() -> Settings:
    """Build settings from the environment. Kept as a function for easy test overrides."""
    return Settings()
