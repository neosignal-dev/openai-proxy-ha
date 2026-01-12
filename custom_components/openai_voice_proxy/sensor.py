"""Sensor platform for OpenAI Voice Assistant Proxy."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, CONF_ASSISTANT_NAME, DEFAULT_ASSISTANT_NAME

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    from .const import DOMAIN
    manager = hass.data[DOMAIN][config_entry.entry_id]
    
    # Create coordinator for metrics updates
    coordinator = MetricsCoordinator(hass, manager)
    await coordinator.async_config_entry_first_refresh()
    
    # Create sensor entities
    entities = [
        OpenAIProxyHealthSensor(coordinator, config_entry),
        OpenAIProxyRequestsSensor(coordinator, config_entry),
        OpenAIProxyTokensSensor(coordinator, config_entry),
    ]
    
    async_add_entities(entities)
    _LOGGER.info("Sensor entities added")


class MetricsCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching metrics from FastAPI server."""

    def __init__(self, hass: HomeAssistant, manager) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.manager = manager

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from FastAPI metrics endpoint."""
        try:
            metrics_data = await self.manager.get_metrics()
            
            # Parse Prometheus metrics
            metrics = self._parse_prometheus_metrics(metrics_data.get("metrics", ""))
            
            return {
                "health": "healthy" if "error" not in metrics_data else "unhealthy",
                "requests_total": metrics.get("http_requests_total", 0),
                "tokens_used": metrics.get("openai_tokens_used_total", 0),
                "commands_processed": metrics.get("commands_processed_total", 0),
                "websocket_connections": metrics.get("active_websocket_connections", 0),
            }
            
        except Exception as err:
            _LOGGER.error("Error fetching metrics: %s", err)
            raise UpdateFailed(f"Error fetching metrics: {err}") from err

    def _parse_prometheus_metrics(self, metrics_text: str) -> dict[str, float]:
        """Parse Prometheus metrics text format."""
        metrics = {}
        for line in metrics_text.split("\n"):
            if line.startswith("#") or not line.strip():
                continue
            
            try:
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0].split("{")[0]
                    metric_value = float(parts[-1])
                    
                    # Sum up metrics with same name
                    if metric_name in metrics:
                        metrics[metric_name] += metric_value
                    else:
                        metrics[metric_name] = metric_value
            except (ValueError, IndexError):
                continue
        
        return metrics


class OpenAIProxyHealthSensor(CoordinatorEntity, SensorEntity):
    """Sensor for OpenAI Proxy health status."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MetricsCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_health"
        self._attr_name = "Health Status"
        self._attr_device_class = None
        self._entry = entry

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("health", "unknown")

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.native_value == "healthy":
            return "mdi:check-circle"
        return "mdi:alert-circle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            "assistant_name": self._entry.data.get(
                CONF_ASSISTANT_NAME, DEFAULT_ASSISTANT_NAME
            ),
            "websocket_connections": self.coordinator.data.get(
                "websocket_connections", 0
            ),
        }


class OpenAIProxyRequestsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for total HTTP requests."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: MetricsCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_requests"
        self._attr_name = "Total Requests"
        self._attr_native_unit_of_measurement = "requests"
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return int(self.coordinator.data.get("requests_total", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            "commands_processed": self.coordinator.data.get("commands_processed", 0),
        }


class OpenAIProxyTokensSensor(CoordinatorEntity, SensorEntity):
    """Sensor for total OpenAI tokens used."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: MetricsCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_tokens"
        self._attr_name = "Tokens Used"
        self._attr_native_unit_of_measurement = "tokens"
        self._attr_icon = "mdi:file-word-box"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return int(self.coordinator.data.get("tokens_used", 0))
