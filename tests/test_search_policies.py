"""Tests for search recency policies"""

import pytest
from app.services.search.policies import (
    RecencyPolicy,
    PreClassifier,
    SearchCategory,
    RecencyRequirement,
)


class TestRecencyPolicy:
    """Test RecencyPolicy"""

    @pytest.fixture
    def policy(self):
        return RecencyPolicy()

    def test_get_policy_news(self, policy):
        """Test policy for news category"""
        pol = policy.get_policy(SearchCategory.NEWS)
        assert pol["requirement"] == RecencyRequirement.MANDATORY
        assert pol["max_days"] == 7

    def test_get_policy_historical(self, policy):
        """Test policy for historical category"""
        pol = policy.get_policy(SearchCategory.HISTORICAL)
        assert pol["requirement"] == RecencyRequirement.FORBIDDEN
        assert pol["max_days"] is None

    def test_enforce_mandatory_recency(self, policy):
        """Test enforcement of mandatory recency"""
        decision = policy.enforce_recency(SearchCategory.NEWS, requested_days=None)
        
        assert decision["recency_days"] is not None
        assert decision["enforced"] is True
        assert decision["requirement"] == RecencyRequirement.MANDATORY.value

    def test_enforce_mandatory_override(self, policy):
        """Test mandatory policy overrides requested days"""
        decision = policy.enforce_recency(SearchCategory.NEWS, requested_days=365)
        
        # Should override with preferred days
        assert decision["recency_days"] <= 7
        assert decision["enforced"] is True

    def test_enforce_forbidden_recency(self, policy):
        """Test enforcement of forbidden recency"""
        decision = policy.enforce_recency(SearchCategory.HISTORICAL, requested_days=7)
        
        assert decision["recency_days"] is None
        assert decision["enforced"] is True

    def test_validate_override_mandatory(self, policy):
        """Test that mandatory policies cannot be overridden"""
        allowed = policy.validate_override(
            SearchCategory.NEWS,
            override_days=365,
            reason="I want old news",
        )
        
        assert allowed is False

    def test_validate_override_recommended(self, policy):
        """Test that recommended policies can be overridden with reason"""
        allowed = policy.validate_override(
            SearchCategory.TUTORIALS,
            override_days=730,
            reason="Looking for comprehensive tutorial from 2 years ago",
        )
        
        assert allowed is True

    def test_validate_override_insufficient_reason(self, policy):
        """Test override rejection with insufficient reason"""
        allowed = policy.validate_override(
            SearchCategory.TUTORIALS,
            override_days=730,
            reason="want old",
        )
        
        assert allowed is False  # Reason too short


class TestPreClassifier:
    """Test PreClassifier"""

    @pytest.fixture
    def classifier(self):
        return PreClassifier()

    def test_classify_news(self, classifier):
        """Test classification of news queries"""
        category = classifier.classify("новости про AI сегодня")
        assert category == SearchCategory.NEWS

    def test_classify_weather(self, classifier):
        """Test classification of weather queries"""
        category = classifier.classify("какая погода в Москве")
        assert category == SearchCategory.WEATHER

    def test_classify_transport(self, classifier):
        """Test classification of transport queries"""
        category = classifier.classify("расписание электричек")
        assert category == SearchCategory.TRANSPORT

    def test_classify_stocks(self, classifier):
        """Test classification of stock queries"""
        category = classifier.classify("курс акций Tesla")
        assert category == SearchCategory.STOCKS

    def test_classify_tech_docs(self, classifier):
        """Test classification of tech docs queries"""
        category = classifier.classify("документация FastAPI")
        assert category == SearchCategory.TECH_DOCS

    def test_classify_tutorials(self, classifier):
        """Test classification of tutorial queries"""
        category = classifier.classify("как настроить Docker")
        assert category == SearchCategory.TUTORIALS

    def test_classify_shopping(self, classifier):
        """Test classification of shopping queries"""
        category = classifier.classify("купить iPhone 15 цена")
        assert category == SearchCategory.SHOPPING

    def test_classify_historical(self, classifier):
        """Test classification of historical queries"""
        category = classifier.classify("когда был основан Рим")
        assert category == SearchCategory.HISTORICAL

    def test_classify_general(self, classifier):
        """Test classification of general queries"""
        category = classifier.classify("какие-то общие вопросы")
        assert category == SearchCategory.GENERAL
