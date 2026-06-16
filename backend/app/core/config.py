from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise AI Operations Copilot"
    environment: str = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://copilot:copilot@db:5432/copilot",
        alias="DATABASE_URL",
    )
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    chat_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_CHAT_MODEL")
    embedding_model: str = Field(default="text-embedding-3-large", alias="OPENAI_EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    local_llm_base_url: str | None = Field(default=None, alias="LOCAL_LLM_BASE_URL")
    local_llm_api_key: str = Field(default="local", alias="LOCAL_LLM_API_KEY")
    local_chat_model: str = Field(default="local-model", alias="LOCAL_CHAT_MODEL")
    local_embedding_base_url: str | None = Field(default=None, alias="LOCAL_EMBEDDING_BASE_URL")
    local_embedding_model: str | None = Field(default=None, alias="LOCAL_EMBEDDING_MODEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
