"""Pytest configuration and fixtures"""

import pytest
import asyncio
from typing import AsyncGenerator


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_user_id() -> str:
    """Sample user ID for tests"""
    return "test_user_123"


@pytest.fixture
def sample_command() -> str:
    """Sample user command"""
    return "Включи свет в гостиной"


@pytest.fixture
def sample_ha_context() -> dict:
    """Sample Home Assistant context"""
    return {
        "config": {"location_name": "Home"},
        "total_entities": 10,
        "areas": ["living_room", "bedroom", "kitchen"],
        "entities_by_domain": {
            "light": [
                {"entity_id": "light.living_room", "state": "off"},
                {"entity_id": "light.bedroom", "state": "on"},
            ],
            "switch": [
                {"entity_id": "switch.fan", "state": "off"},
            ],
        },
        "entities_by_area": {
            "living_room": [
                {"entity_id": "light.living_room", "domain": "light"},
            ],
        },
    }
