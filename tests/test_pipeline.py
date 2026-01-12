"""Tests for pipeline components"""

import pytest
from app.services.pipeline.intent_analyzer import IntentAnalyzer, IntentType
from app.services.pipeline.context_resolver import ContextResolver


class TestIntentAnalyzer:
    """Test IntentAnalyzer"""

    @pytest.fixture
    def analyzer(self):
        return IntentAnalyzer()

    def test_quick_classify_ha_control(self, analyzer):
        """Test quick classification for HA control"""
        result = analyzer._quick_classify("Включи свет")
        assert result is not None
        assert result["type"] == IntentType.HA_CONTROL
        assert result["confidence"] >= 0.8

    def test_quick_classify_web_search(self, analyzer):
        """Test quick classification for web search"""
        result = analyzer._quick_classify("Найди информацию про AI")
        assert result is not None
        assert result["type"] == IntentType.WEB_SEARCH
        assert result["confidence"] >= 0.85

    def test_quick_classify_habr_search(self, analyzer):
        """Test quick classification for Habr search"""
        result = analyzer._quick_classify("Найди статью на хабре про Python")
        assert result is not None
        assert result["type"] == IntentType.HABR_SEARCH
        assert result["confidence"] >= 0.95

    def test_quick_classify_memory_query(self, analyzer):
        """Test quick classification for memory query"""
        result = analyzer._quick_classify("Помнишь, что я говорил вчера?")
        assert result is not None
        assert result["type"] == IntentType.MEMORY_QUERY
        assert result["confidence"] >= 0.90

    def test_should_use_search(self, analyzer):
        """Test search requirement detection"""
        intent = {"type": IntentType.WEB_SEARCH}
        assert analyzer.should_use_search(intent) is True

        intent = {"type": IntentType.HA_CONTROL}
        assert analyzer.should_use_search(intent) is False

    def test_should_use_ha(self, analyzer):
        """Test HA requirement detection"""
        intent = {"type": IntentType.HA_CONTROL}
        assert analyzer.should_use_ha(intent) is True

        intent = {"type": IntentType.WEB_SEARCH}
        assert analyzer.should_use_ha(intent) is False


class TestContextResolver:
    """Test ContextResolver"""

    @pytest.fixture
    def resolver(self):
        return ContextResolver()

    def test_extract_entities_by_domain(self, resolver, sample_ha_context):
        """Test entity extraction by domain"""
        entities = resolver.extract_entities_from_ha(
            sample_ha_context,
            domain="light",
        )
        assert len(entities) == 2
        assert all(e["entity_id"].startswith("light.") for e in entities)

    def test_extract_entities_by_area(self, resolver, sample_ha_context):
        """Test entity extraction by area"""
        entities = resolver.extract_entities_from_ha(
            sample_ha_context,
            area="living_room",
        )
        assert len(entities) >= 1
        assert any("living_room" in e["entity_id"] for e in entities)

    def test_format_context_for_llm(self, resolver, sample_ha_context):
        """Test context formatting"""
        context = {
            "intent": {"type": "ha_control"},
            "ha": sample_ha_context,
            "memory": {
                "relevant_rules": [
                    {"rule_text": "Всегда спрашивай перед выключением"},
                ],
                "relevant_memories": [],
            },
        }

        formatted = resolver.format_context_for_llm(context)
        assert "Намерение" in formatted
        assert "10" in formatted  # total entities
        assert "Правила" in formatted
