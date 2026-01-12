"""Config flow for OpenAI Voice Assistant Proxy integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
    CONF_PERPLEXITY_API_KEY,
    CONF_ASSISTANT_NAME,
    CONF_OPENAI_TTS_VOICE,
    CONF_TELEGRAM_BOT_TOKEN,
    CONF_TELEGRAM_CHAT_ID,
    CONF_LOG_LEVEL,
    CONF_RATE_LIMIT,
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_TTS_VOICE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_RATE_LIMIT,
    TTS_VOICES,
    LOG_LEVELS,
)

_LOGGER = logging.getLogger(__name__)


class OpenAIVoiceProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAI Voice Assistant Proxy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # Basic validation - just check if key is provided
            if not user_input.get(CONF_OPENAI_API_KEY):
                errors["base"] = "invalid_api_key"
            else:
                # API key validation will happen during setup
                return self.async_create_entry(
                    title=user_input.get(CONF_ASSISTANT_NAME, DEFAULT_ASSISTANT_NAME),
                    data=user_input,
                )

        data_schema = vol.Schema({
            vol.Required(CONF_OPENAI_API_KEY): str,
            vol.Optional(CONF_PERPLEXITY_API_KEY): str,
            vol.Optional(
                CONF_ASSISTANT_NAME,
                default=DEFAULT_ASSISTANT_NAME
            ): str,
            vol.Optional(
                CONF_OPENAI_TTS_VOICE,
                default=DEFAULT_TTS_VOICE
            ): vol.In(TTS_VOICES),
            vol.Optional(CONF_TELEGRAM_BOT_TOKEN): str,
            vol.Optional(CONF_TELEGRAM_CHAT_ID): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OpenAIVoiceProxyOptionsFlow:
        """Get the options flow for this handler."""
        return OpenAIVoiceProxyOptionsFlow(config_entry)


class OpenAIVoiceProxyOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for OpenAI Voice Assistant Proxy."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(
                CONF_ASSISTANT_NAME,
                default=self.config_entry.data.get(
                    CONF_ASSISTANT_NAME, DEFAULT_ASSISTANT_NAME
                )
            ): str,
            vol.Optional(
                CONF_OPENAI_TTS_VOICE,
                default=self.config_entry.data.get(
                    CONF_OPENAI_TTS_VOICE, DEFAULT_TTS_VOICE
                )
            ): vol.In(TTS_VOICES),
            vol.Optional(
                CONF_LOG_LEVEL,
                default=self.config_entry.options.get(
                    CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL
                )
            ): vol.In(LOG_LEVELS),
            vol.Optional(
                CONF_RATE_LIMIT,
                default=self.config_entry.options.get(
                    CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT
                )
            ): cv.positive_int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
