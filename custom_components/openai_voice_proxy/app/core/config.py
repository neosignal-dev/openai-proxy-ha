"""Configuration management using Pydantic settings"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_tts_model: str = Field(
        default="tts-1-hd", description="OpenAI TTS model"
    )
    openai_tts_voice: str = Field(
        default="alloy", description="OpenAI TTS voice (alloy, echo, fable, onyx, nova, shimmer)"
    )
    openai_realtime_model: str = Field(
        default="gpt-4o-realtime-preview", description="OpenAI Realtime model"
    )

    # Home Assistant
    ha_url: str = Field(..., description="Home Assistant URL")
    ha_token: str = Field(..., description="Home Assistant long-lived access token")
    ha_websocket_url: Optional[str] = Field(
        default=None, description="Home Assistant WebSocket URL"
    )

    # Perplexity
    perplexity_api_key: str = Field(..., description="Perplexity API key")
    perplexity_model: str = Field(
        default="llama-3.1-sonar-large-128k-online",
        description="Perplexity model"
    )
    perplexity_default_recency_days: int = Field(
        default=7, description="Default recency in days"
    )

    # Telegram
    telegram_bot_token: Optional[str] = Field(
        default=None, description="Telegram bot token"
    )
    telegram_chat_id: Optional[str] = Field(
        default=None, description="Telegram chat ID"
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/openai_proxy.db",
        description="Database URL"
    )
    chroma_persist_dir: str = Field(
        default="./chroma_data", description="Chroma persist directory"
    )

    # Memory
    short_term_memory_size: int = Field(
        default=20, description="Number of messages in short-term memory"
    )
    long_term_memory_enabled: bool = Field(
        default=True, description="Enable long-term memory"
    )

    # Security
    allowed_ha_services: str = Field(
        default="light.turn_on,light.turn_off,switch.turn_on,switch.turn_off,cover.open_cover,cover.close_cover,climate.set_temperature,scene.turn_on",
        description="Comma-separated list of allowed HA services"
    )
    require_confirmation_services: str = Field(
        default="alarm_control_panel.*,lock.*,cover.*",
        description="Comma-separated list of services requiring confirmation (supports wildcards)"
    )

    # Rate limiting
    rate_limit_per_minute: int = Field(
        default=60, description="General rate limit per minute"
    )
    perplexity_rate_limit_per_minute: int = Field(
        default=20, description="Perplexity API rate limit"
    )
    habr_rate_limit_per_minute: int = Field(
        default=10, description="Habr scraping rate limit"
    )

    # Cache
    habr_cache_ttl_minutes: int = Field(
        default=60, description="Habr cache TTL in minutes"
    )
    perplexity_cache_ttl_minutes: int = Field(
        default=30, description="Perplexity cache TTL in minutes"
    )

    # Assistant personality
    assistant_name: str = Field(default="Домовой", description="Assistant name")
    assistant_language: str = Field(default="ru", description="Assistant language")
    assistant_style: str = Field(
        default="friendly,concise,helpful", description="Assistant style"
    )

    @property
    def allowed_services_list(self) -> List[str]:
        """Parse allowed services into list"""
        return [s.strip() for s in self.allowed_ha_services.split(",")]

    @property
    def confirmation_services_list(self) -> List[str]:
        """Parse confirmation services into list"""
        return [s.strip() for s in self.require_confirmation_services.split(",")]

    @property
    def assistant_style_list(self) -> List[str]:
        """Parse assistant style into list"""
        return [s.strip() for s in self.assistant_style.split(",")]


# Global settings instance
settings = Settings()


