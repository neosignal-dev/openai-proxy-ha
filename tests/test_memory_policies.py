"""Tests for memory policies"""

import pytest
from datetime import datetime, timedelta
from app.services.memory_v2.policy import (
    MemoryPolicy,
    MemoryType,
    MemoryImportance,
)


class TestMemoryPolicy:
    """Test MemoryPolicy"""

    @pytest.fixture
    def policy(self):
        return MemoryPolicy()

    def test_should_save_empty_content(self, policy):
        """Test rejection of empty content"""
        assert policy.should_save("", MemoryType.CONVERSATION) is False
        assert policy.should_save("  ", MemoryType.CONVERSATION) is False

    def test_should_save_short_ack(self, policy):
        """Test rejection of short acknowledgments"""
        assert policy.should_save("ok", MemoryType.CONVERSATION) is False
        assert policy.should_save("да", MemoryType.CONVERSATION) is False
        assert policy.should_save("нет", MemoryType.CONVERSATION) is False

    def test_should_save_rule(self, policy):
        """Test saving of rules"""
        assert policy.should_save("Запомни это правило", MemoryType.RULE) is True

    def test_should_save_long_conversation(self, policy):
        """Test saving of long conversations"""
        long_text = "Это длинная беседа " * 10
        assert policy.should_save(long_text, MemoryType.CONVERSATION) is True

    def test_determine_importance_rule(self, policy):
        """Test importance of rules"""
        importance = policy.determine_importance(
            "Всегда спрашивай подтверждение",
            MemoryType.RULE,
        )
        assert importance == MemoryImportance.CRITICAL

    def test_determine_importance_action(self, policy):
        """Test importance of actions"""
        importance = policy.determine_importance(
            "Включил свет в спальне",
            MemoryType.ACTION,
        )
        assert importance == MemoryImportance.HIGH

    def test_determine_importance_with_keywords(self, policy):
        """Test importance detection by keywords"""
        importance = policy.determine_importance(
            "Это очень важно запомнить",
            MemoryType.CONVERSATION,
        )
        assert importance == MemoryImportance.HIGH

    def test_should_save_to_short_term(self, policy):
        """Test short-term storage decision"""
        assert policy.should_save_to_short_term(MemoryImportance.LOW) is True
        assert policy.should_save_to_short_term(MemoryImportance.CRITICAL) is True

    def test_should_save_to_long_term(self, policy):
        """Test long-term storage decision"""
        assert policy.should_save_to_long_term(MemoryImportance.LOW) is False
        assert policy.should_save_to_long_term(MemoryImportance.MEDIUM) is True
        assert policy.should_save_to_long_term(MemoryImportance.CRITICAL) is True

    def test_get_retention_days(self, policy):
        """Test retention period calculation"""
        assert policy.get_retention_days(MemoryImportance.LOW) == 1
        assert policy.get_retention_days(MemoryImportance.MEDIUM) == 7
        assert policy.get_retention_days(MemoryImportance.HIGH) == 30
        assert policy.get_retention_days(MemoryImportance.CRITICAL) is None

    def test_get_expiration_date(self, policy):
        """Test expiration date calculation"""
        now = datetime.utcnow()
        
        expires = policy.get_expiration_date(MemoryImportance.LOW, now)
        assert expires == now + timedelta(days=1)
        
        expires = policy.get_expiration_date(MemoryImportance.CRITICAL, now)
        assert expires is None  # Never expires

    def test_classify_rule_content(self, policy):
        """Test content classification - rule"""
        memory_type = policy.classify_content("Запомни это правило", "user")
        assert memory_type == MemoryType.RULE

    def test_classify_preference_content(self, policy):
        """Test content classification - preference"""
        memory_type = policy.classify_content("Я предпочитаю тёплый свет", "user")
        assert memory_type == MemoryType.PREFERENCE

    def test_classify_conversation_content(self, policy):
        """Test content classification - conversation"""
        memory_type = policy.classify_content("Привет, как дела?", "user")
        assert memory_type == MemoryType.CONVERSATION

    def test_should_cleanup_expired(self, policy):
        """Test cleanup decision for expired memory"""
        past = datetime.utcnow() - timedelta(days=10)
        
        memory = {
            "expires_at": past.isoformat(),
            "importance": MemoryImportance.LOW,
        }
        
        assert policy.should_cleanup(memory) is True

    def test_should_not_cleanup_critical(self, policy):
        """Test that critical memories are never cleaned up"""
        past = datetime.utcnow() - timedelta(days=365)
        
        memory = {
            "expires_at": past.isoformat(),
            "importance": MemoryImportance.CRITICAL,
        }
        
        assert policy.should_cleanup(memory) is False
