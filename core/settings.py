from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VERSION = (ROOT / "contracts" / "VERSION").read_text().strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Village Core"
    village_layers: str = Field(default="0", alias="VILLAGE_LAYERS")
    village_llm: str = Field(default="off", alias="VILLAGE_LLM")
    surreal_db_url: str = Field(default="", alias="SURREAL_DB_URL")
    surreal_db_ns: str = Field(default="village", alias="SURREAL_DB_NS")
    surreal_db_db: str = Field(default="main", alias="SURREAL_DB_DB")
    surreal_db_user: str = Field(default="", alias="SURREAL_DB_USER")
    surreal_db_pass: str = Field(default="", alias="SURREAL_DB_PASS")
    admin_key: str = Field(default="change-me-admin-key", alias="ADMIN_KEY")
    demo_clock: str = Field(default="2026-10-16T20:50:00-04:00", alias="DEMO_CLOCK")
    bedrock_sonnet_model: str = Field(default="anthropic.claude-sonnet-5-5", alias="BEDROCK_SONNET_MODEL")
    bedrock_haiku_model: str = Field(default="anthropic.claude-haiku-5-5", alias="BEDROCK_HAIKU_MODEL")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    @property
    def layers(self) -> list[int]:
        raw = self.village_layers.strip()
        if not raw:
            return []
        return [int(part) for part in raw.split(",") if part.strip().isdigit()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
