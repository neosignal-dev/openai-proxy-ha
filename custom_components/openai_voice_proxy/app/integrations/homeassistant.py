"""Home Assistant integration"""

import re
from typing import Dict, List, Optional, Any
import aiohttp
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class HomeAssistantClient:
    """Client for Home Assistant REST API"""

    def __init__(self):
        self.url = settings.ha_url.rstrip("/")
        self.token = settings.ha_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Any:
        """Make HTTP request to HA API
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            Response data
        """
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)

        url = f"{self.url}/api/{endpoint.lstrip('/')}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                
                if response.content_type == "application/json":
                    return await response.json()
                return await response.text()

        except aiohttp.ClientError as e:
            logger.error("HA API request failed", method=method, url=url, error=str(e))
            raise

    async def get_states(self, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get entity states
        
        Args:
            entity_id: Optional specific entity ID
            
        Returns:
            List of entity states
        """
        if entity_id:
            endpoint = f"states/{entity_id}"
            result = await self._request("GET", endpoint)
            return [result] if result else []
        else:
            return await self._request("GET", "states")

    async def get_services(self) -> Dict[str, Any]:
        """Get available services
        
        Returns:
            Dictionary of available services by domain
        """
        return await self._request("GET", "services")

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None,
        target: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Call Home Assistant service
        
        Args:
            domain: Service domain (e.g., "light")
            service: Service name (e.g., "turn_on")
            service_data: Service data
            target: Target entities/areas/devices
            
        Returns:
            List of affected entity states
        """
        service_call = f"{domain}.{service}"
        
        # Check if service is allowed
        allowed_services = settings.allowed_services_list
        if not self._is_service_allowed(service_call, allowed_services):
            raise PermissionError(f"Service {service_call} is not allowed")

        logger.info(
            "Calling HA service",
            domain=domain,
            service=service,
            service_data=service_data,
            target=target,
        )

        data = {}
        if service_data:
            data.update(service_data)
        if target:
            data.update(target)

        endpoint = f"services/{domain}/{service}"
        return await self._request("POST", endpoint, json=data)

    def _is_service_allowed(self, service: str, allowed: List[str]) -> bool:
        """Check if service is in allowed list
        
        Args:
            service: Service to check (domain.service)
            allowed: List of allowed services (supports wildcards)
            
        Returns:
            True if allowed
        """
        for pattern in allowed:
            # Convert wildcard pattern to regex
            regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
            if re.match(f"^{regex_pattern}$", service):
                return True
        return False

    def needs_confirmation(self, service: str) -> bool:
        """Check if service needs user confirmation
        
        Args:
            service: Service to check (domain.service)
            
        Returns:
            True if confirmation required
        """
        confirmation_services = settings.confirmation_services_list
        return self._is_service_allowed(service, confirmation_services)

    async def get_config(self) -> Dict[str, Any]:
        """Get Home Assistant configuration
        
        Returns:
            Configuration dictionary
        """
        return await self._request("GET", "config")

    async def get_areas(self) -> List[Dict[str, Any]]:
        """Get all areas
        
        Returns:
            List of areas
        """
        # Note: Areas API might require different endpoint depending on HA version
        try:
            return await self._request("GET", "areas")
        except Exception as e:
            logger.warning("Failed to fetch areas", error=str(e))
            return []

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices
        
        Returns:
            List of devices
        """
        try:
            return await self._request("GET", "devices")
        except Exception as e:
            logger.warning("Failed to fetch devices", error=str(e))
            return []

    async def get_context(self) -> Dict[str, Any]:
        """Get full HA context (states, areas, devices)
        
        Returns:
            Complete context dictionary
        """
        logger.info("Fetching HA context")
        
        states = await self.get_states()
        config = await self.get_config()
        areas = await self.get_areas()
        devices = await self.get_devices()

        # Organize by domain and area
        entities_by_domain: Dict[str, List[Dict[str, Any]]] = {}
        entities_by_area: Dict[str, List[Dict[str, Any]]] = {}

        for state in states:
            entity_id = state.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            
            # Group by domain
            if domain not in entities_by_domain:
                entities_by_domain[domain] = []
            entities_by_domain[domain].append(state)

            # Group by area (if available)
            area = state.get("attributes", {}).get("area_id")
            if area:
                if area not in entities_by_area:
                    entities_by_area[area] = []
                entities_by_area[area].append(state)

        context = {
            "config": config,
            "areas": areas,
            "devices": devices,
            "states": states,
            "entities_by_domain": entities_by_domain,
            "entities_by_area": entities_by_area,
            "total_entities": len(states),
        }

        logger.info(
            "HA context retrieved",
            total_entities=len(states),
            domains=len(entities_by_domain),
            areas=len(areas),
        )

        return context

    async def find_user_location(self, user_id: str = "default") -> Optional[str]:
        """Find current user location based on presence sensors
        
        Args:
            user_id: User identifier
            
        Returns:
            Area ID or None
        """
        try:
            states = await self.get_states()
            
            # Look for person or device_tracker entities
            for state in states:
                entity_id = state.get("entity_id", "")
                
                if entity_id.startswith("person.") or entity_id.startswith("device_tracker."):
                    location = state.get("state")
                    if location and location != "not_home":
                        logger.info("User location found", user_id=user_id, location=location)
                        return location

            logger.info("User location not found", user_id=user_id)
            return None

        except Exception as e:
            logger.error("Failed to find user location", error=str(e))
            return None

    async def get_entities_in_area(self, area_id: str) -> List[Dict[str, Any]]:
        """Get all entities in specific area
        
        Args:
            area_id: Area identifier
            
        Returns:
            List of entity states
        """
        states = await self.get_states()
        entities = []

        for state in states:
            area = state.get("attributes", {}).get("area_id")
            if area == area_id:
                entities.append(state)

        logger.info("Entities in area found", area_id=area_id, count=len(entities))
        return entities

    async def create_automation(
        self,
        automation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create automation via HA API
        
        Args:
            automation_config: Automation configuration
            
        Returns:
            Result of automation creation
        """
        logger.info("Creating automation", config=automation_config)
        
        # Call automation.reload service after creating config
        # Note: This typically requires writing to config files
        # For security, this might need special handling
        
        # For now, return the config as-is
        # In production, you'd write to automations.yaml and reload
        
        return {
            "success": True,
            "automation": automation_config,
            "message": "Automation configuration generated. Manual review recommended.",
        }


# Global client instance
ha_client = HomeAssistantClient()


