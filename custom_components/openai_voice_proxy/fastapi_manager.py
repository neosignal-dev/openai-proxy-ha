"""FastAPI server manager for OpenAI Voice Assistant Proxy."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_OPENAI_API_KEY,
    CONF_PERPLEXITY_API_KEY,
    CONF_ASSISTANT_NAME,
    CONF_OPENAI_TTS_VOICE,
    CONF_TELEGRAM_BOT_TOKEN,
    CONF_TELEGRAM_CHAT_ID,
    CONF_LOG_LEVEL,
    DEFAULT_ASSISTANT_NAME,
    DEFAULT_TTS_VOICE,
    DEFAULT_LOG_LEVEL,
    FASTAPI_HOST,
    FASTAPI_PORT,
)

_LOGGER = logging.getLogger(__name__)


class FastAPIManager:
    """Manager for FastAPI server."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the FastAPI manager."""
        self.hass = hass
        self.entry = entry
        self.server_task: asyncio.Task | None = None
        self._base_url = f"http://{FASTAPI_HOST}:{FASTAPI_PORT}"
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        """Start the FastAPI server."""
        _LOGGER.info("Starting FastAPI server")
        
        # Set environment variables from config
        os.environ["OPENAI_API_KEY"] = self.entry.data[CONF_OPENAI_API_KEY]
        
        # Get Home Assistant URL (prefer internal, fallback to external)
        ha_url = self.hass.config.internal_url or self.hass.config.external_url or "http://homeassistant.local:8123"
        os.environ["HA_URL"] = ha_url
        
        # Get HA token - create a long-lived token or use existing
        # For now, we'll use empty and rely on internal network access
        os.environ["HA_TOKEN"] = os.environ.get("SUPERVISOR_TOKEN", "")
        
        # Optional: Perplexity API
        if CONF_PERPLEXITY_API_KEY in self.entry.data and self.entry.data[CONF_PERPLEXITY_API_KEY]:
            os.environ["PERPLEXITY_API_KEY"] = self.entry.data[CONF_PERPLEXITY_API_KEY]
        else:
            os.environ["PERPLEXITY_API_KEY"] = ""
        
        # Assistant configuration
        os.environ["ASSISTANT_NAME"] = self.entry.data.get(
            CONF_ASSISTANT_NAME, DEFAULT_ASSISTANT_NAME
        )
        os.environ["OPENAI_TTS_VOICE"] = self.entry.data.get(
            CONF_OPENAI_TTS_VOICE, DEFAULT_TTS_VOICE
        )
        
        # Optional: Telegram
        if CONF_TELEGRAM_BOT_TOKEN in self.entry.data and self.entry.data[CONF_TELEGRAM_BOT_TOKEN]:
            os.environ["TELEGRAM_BOT_TOKEN"] = self.entry.data[CONF_TELEGRAM_BOT_TOKEN]
        else:
            os.environ["TELEGRAM_BOT_TOKEN"] = ""
            
        if CONF_TELEGRAM_CHAT_ID in self.entry.data and self.entry.data[CONF_TELEGRAM_CHAT_ID]:
            os.environ["TELEGRAM_CHAT_ID"] = self.entry.data[CONF_TELEGRAM_CHAT_ID]
        else:
            os.environ["TELEGRAM_CHAT_ID"] = ""
        
        os.environ["LOG_LEVEL"] = self.entry.options.get(
            CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL
        )
        os.environ["HOST"] = FASTAPI_HOST
        os.environ["PORT"] = str(FASTAPI_PORT)
        
        # Create aiohttp session
        self._session = aiohttp.ClientSession()
        
        # Start FastAPI server in background
        self.server_task = asyncio.create_task(self._run_server())
        
        # Wait for server to be ready
        await self._wait_for_server()
        
        _LOGGER.info("FastAPI server started successfully")

    async def _run_server(self) -> None:
        """Run the FastAPI server."""
        try:
            import uvicorn
            from app.main_v2 import app
            
            config = uvicorn.Config(
                app,
                host=FASTAPI_HOST,
                port=FASTAPI_PORT,
                log_level=os.environ.get("LOG_LEVEL", "info").lower(),
                access_log=False,
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as err:
            _LOGGER.error("FastAPI server error: %s", err)
            raise

    async def _wait_for_server(self, timeout: int = 30) -> None:
        """Wait for server to be ready."""
        _LOGGER.debug("Waiting for FastAPI server to be ready")
        
        for _ in range(timeout):
            try:
                async with self._session.get(
                    f"{self._base_url}/healthz",
                    timeout=aiohttp.ClientTimeout(total=1)
                ) as response:
                    if response.status == 200:
                        _LOGGER.info("FastAPI server is ready")
                        return
            except (aiohttp.ClientError, asyncio.TimeoutError):
                await asyncio.sleep(1)
        
        raise TimeoutError("FastAPI server did not start in time")

    async def stop(self) -> None:
        """Stop the FastAPI server."""
        _LOGGER.info("Stopping FastAPI server")
        
        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
        
        if self._session:
            await self._session.close()
        
        _LOGGER.info("FastAPI server stopped")

    async def process_command(
        self,
        user_id: str,
        command: str,
        conversation_id: str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        """Process a command through the FastAPI backend."""
        try:
            payload = {
                "user_id": user_id,
                "command": command,
                "language": language,
            }
            if conversation_id:
                payload["conversation_id"] = conversation_id
            
            async with self._session.post(
                f"{self._base_url}/v1/command",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except Exception as err:
            _LOGGER.error("Error processing command: %s", err)
            return {"error": str(err)}

    async def search(self, query: str) -> dict[str, Any]:
        """Perform web search through Perplexity."""
        try:
            async with self._session.post(
                f"{self._base_url}/v1/search",
                json={"query": query},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Error performing search: %s", err)
            return {"error": str(err)}

    async def send_telegram(self, message: str, parse_mode: str = "Markdown") -> None:
        """Send message to Telegram."""
        try:
            async with self._session.post(
                f"{self._base_url}/v1/telegram/send",
                json={"message": message, "parse_mode": parse_mode},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
        except Exception as err:
            _LOGGER.error("Error sending telegram message: %s", err)

    async def search_habr(
        self, query: str, tags: str | None = None, days: int = 30
    ) -> dict[str, Any]:
        """Search Habr.com."""
        try:
            params = {"query": query, "days": days}
            if tags:
                params["tags"] = tags
            
            async with self._session.get(
                f"{self._base_url}/v1/habr/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Error searching Habr: %s", err)
            return {"error": str(err)}

    async def get_ha_context(self) -> dict[str, Any]:
        """Get Home Assistant context."""
        try:
            async with self._session.get(
                f"{self._base_url}/v1/context",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as err:
            _LOGGER.error("Error getting HA context: %s", err)
            return {"error": str(err)}

    async def get_metrics(self) -> dict[str, Any]:
        """Get Prometheus metrics."""
        try:
            async with self._session.get(
                f"{self._base_url}/metrics",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                response.raise_for_status()
                text = await response.text()
                return {"metrics": text}
        except Exception as err:
            _LOGGER.error("Error getting metrics: %s", err)
            return {"error": str(err)}
