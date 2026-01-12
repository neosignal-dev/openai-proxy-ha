"""The OpenAI Voice Assistant Proxy integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_SEARCH,
    SERVICE_SEND_TELEGRAM,
    SERVICE_SEARCH_HABR,
    SERVICE_GET_CONTEXT,
)
from .fastapi_manager import FastAPIManager

_LOGGER = logging.getLogger(__name__)

type OpenAIVoiceProxyConfigEntry = ConfigEntry[FastAPIManager]


async def async_setup_entry(hass: HomeAssistant, entry: OpenAIVoiceProxyConfigEntry) -> bool:
    """Set up OpenAI Voice Assistant Proxy from a config entry."""
    _LOGGER.info("Setting up OpenAI Voice Assistant Proxy")
    
    # Create FastAPI manager
    manager = FastAPIManager(hass, entry)
    
    # Start FastAPI server
    try:
        await manager.start()
    except Exception as err:
        _LOGGER.error("Failed to start FastAPI server: %s", err)
        raise ConfigEntryNotReady(f"Failed to start FastAPI server: {err}") from err
    
    # Store manager in runtime data
    entry.runtime_data = manager
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await async_setup_services(hass, manager)
    
    _LOGGER.info("OpenAI Voice Assistant Proxy setup completed")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenAIVoiceProxyConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading OpenAI Voice Assistant Proxy")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Stop FastAPI server
        manager = entry.runtime_data
        await manager.stop()
    
    return unload_ok


async def async_setup_services(hass: HomeAssistant, manager: FastAPIManager) -> None:
    """Set up services for the integration."""
    
    async def handle_search(call: ServiceCall) -> None:
        """Handle search service call."""
        query = call.data.get("query")
        result = await manager.search(query)
        hass.bus.async_fire(
            f"{DOMAIN}_search_result",
            {"query": query, "result": result}
        )
    
    async def handle_send_telegram(call: ServiceCall) -> None:
        """Handle send telegram service call."""
        message = call.data.get("message")
        parse_mode = call.data.get("parse_mode", "Markdown")
        await manager.send_telegram(message, parse_mode)
    
    async def handle_search_habr(call: ServiceCall) -> None:
        """Handle Habr search service call."""
        query = call.data.get("query")
        tags = call.data.get("tags")
        days = call.data.get("days", 30)
        result = await manager.search_habr(query, tags, days)
        hass.bus.async_fire(
            f"{DOMAIN}_habr_result",
            {"query": query, "result": result}
        )
    
    async def handle_get_context(call: ServiceCall) -> None:
        """Handle get context service call."""
        context = await manager.get_ha_context()
        hass.bus.async_fire(
            f"{DOMAIN}_context",
            {"context": context}
        )
    
    # Register services
    hass.services.async_register(DOMAIN, SERVICE_SEARCH, handle_search)
    hass.services.async_register(DOMAIN, SERVICE_SEND_TELEGRAM, handle_send_telegram)
    hass.services.async_register(DOMAIN, SERVICE_SEARCH_HABR, handle_search_habr)
    hass.services.async_register(DOMAIN, SERVICE_GET_CONTEXT, handle_get_context)
    
    _LOGGER.info("Services registered successfully")
