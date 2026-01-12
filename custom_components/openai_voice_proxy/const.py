"""Constants for OpenAI Voice Assistant Proxy."""
from typing import Final

DOMAIN: Final = "openai_voice_proxy"

# Configuration
CONF_OPENAI_API_KEY: Final = "openai_api_key"
CONF_PERPLEXITY_API_KEY: Final = "perplexity_api_key"
CONF_ASSISTANT_NAME: Final = "assistant_name"
CONF_OPENAI_TTS_VOICE: Final = "openai_tts_voice"
CONF_TELEGRAM_BOT_TOKEN: Final = "telegram_bot_token"
CONF_TELEGRAM_CHAT_ID: Final = "telegram_chat_id"
CONF_LOG_LEVEL: Final = "log_level"
CONF_RATE_LIMIT: Final = "rate_limit_per_minute"

# Defaults
DEFAULT_ASSISTANT_NAME: Final = "Домовой"
DEFAULT_TTS_VOICE: Final = "alloy"
DEFAULT_LOG_LEVEL: Final = "INFO"
DEFAULT_RATE_LIMIT: Final = 60

# TTS Voices
TTS_VOICES: Final = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

# Log Levels
LOG_LEVELS: Final = ["DEBUG", "INFO", "WARNING", "ERROR"]

# FastAPI Server
FASTAPI_PORT: Final = 8000
FASTAPI_HOST: Final = "127.0.0.1"

# Services
SERVICE_SEARCH: Final = "search"
SERVICE_SEND_TELEGRAM: Final = "send_telegram"
SERVICE_SEARCH_HABR: Final = "search_habr"
SERVICE_GET_CONTEXT: Final = "get_context"

# Platforms
PLATFORMS: Final = ["conversation", "sensor"]
