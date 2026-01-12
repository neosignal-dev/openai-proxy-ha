"""Conversation platform for OpenAI Voice Assistant Proxy."""
from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

from .const import DOMAIN, CONF_ASSISTANT_NAME, DEFAULT_ASSISTANT_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    manager = config_entry.runtime_data
    agent = OpenAIVoiceAgent(hass, config_entry, manager)
    
    conversation.async_set_agent(hass, config_entry, agent)
    _LOGGER.info("OpenAI Voice conversation agent registered")


class OpenAIVoiceAgent(conversation.AbstractConversationAgent):
    """OpenAI Voice conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, manager) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.manager = manager
        self._attr_supported_languages = ["en", "ru", "es", "fr", "de", "it", "pt", "pl"]

    @property
    def attribution(self):
        """Return the attribution."""
        return {
            "name": self.entry.data.get(CONF_ASSISTANT_NAME, DEFAULT_ASSISTANT_NAME),
            "url": "https://openai.com",
        }

    async def async_process(
        self,
        user_input: conversation.ConversationInput,
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        _LOGGER.debug("Processing conversation input: %s", user_input.text)
        
        # Generate conversation_id if not provided
        conversation_id = user_input.conversation_id
        if conversation_id is None:
            conversation_id = ulid.ulid_now()
        
        try:
            # Process command through FastAPI backend
            result = await self.manager.process_command(
                user_id=user_input.context.user_id or "default",
                command=user_input.text,
                conversation_id=conversation_id,
                language=user_input.language,
            )
            
            # Parse response
            response_text = result.get("response", {}).get("text", "")
            intent_response = result.get("intent_response")
            
            # Determine response type
            if intent_response and intent_response.get("success"):
                response_type = intent.IntentResponseType.ACTION_DONE
            elif result.get("error"):
                response_type = intent.IntentResponseType.ERROR
                response_text = result.get("error", "Unknown error occurred")
            else:
                response_type = intent.IntentResponseType.QUERY_ANSWER
            
            # Create intent response
            intent_result = intent.IntentResponse(language=user_input.language)
            intent_result.response_type = response_type
            intent_result.async_set_speech(response_text)
            
            return conversation.ConversationResult(
                response=intent_result,
                conversation_id=conversation_id,
            )
            
        except Exception as err:
            _LOGGER.error("Error processing conversation: %s", err)
            
            intent_result = intent.IntentResponse(language=user_input.language)
            intent_result.response_type = intent.IntentResponseType.ERROR
            intent_result.async_set_speech(
                f"Sorry, an error occurred: {err}"
            )
            
            return conversation.ConversationResult(
                response=intent_result,
                conversation_id=conversation_id,
            )

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return self._attr_supported_languages
