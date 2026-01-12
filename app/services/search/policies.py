"""Enforced search policies - recency is not optional"""

from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
from app.core.logging import get_logger

logger = get_logger(__name__)


class SearchCategory(str, Enum):
    """Search category types"""
    NEWS = "news"  # Breaking news, current events
    TECH_NEWS = "tech_news"  # Technology news
    WEATHER = "weather"  # Weather queries
    TRANSPORT = "transport"  # Transport schedules
    STOCKS = "stocks"  # Stock prices
    SPORTS = "sports"  # Sports scores
    TECH_DOCS = "tech_docs"  # Technical documentation
    TUTORIALS = "tutorials"  # How-to guides
    SHOPPING = "shopping"  # Product information
    HISTORICAL = "historical"  # Historical facts
    GENERAL = "general"  # General queries


class RecencyRequirement(str, Enum):
    """Recency requirement levels"""
    MANDATORY = "mandatory"  # MUST use recency (news, weather, etc.)
    RECOMMENDED = "recommended"  # SHOULD use recency (tech, tutorials)
    OPTIONAL = "optional"  # MAY use recency (historical, general)
    FORBIDDEN = "forbidden"  # MUST NOT use recency (historical facts)


class RecencyPolicy:
    """
    Enforced recency policy.
    
    LLM CANNOT override these policies.
    These are business rules, not suggestions.
    """

    # Policy definitions
    POLICIES = {
        SearchCategory.NEWS: {
            "requirement": RecencyRequirement.MANDATORY,
            "max_days": 7,
            "preferred_days": 1,
            "reason": "News must be recent to be relevant",
        },
        SearchCategory.TECH_NEWS: {
            "requirement": RecencyRequirement.MANDATORY,
            "max_days": 7,
            "preferred_days": 3,
            "reason": "Technology news ages quickly",
        },
        SearchCategory.WEATHER: {
            "requirement": RecencyRequirement.MANDATORY,
            "max_days": 1,
            "preferred_days": 1,
            "reason": "Weather data must be current",
        },
        SearchCategory.TRANSPORT: {
            "requirement": RecencyRequirement.MANDATORY,
            "max_days": 1,
            "preferred_days": 1,
            "reason": "Transport schedules change frequently",
        },
        SearchCategory.STOCKS: {
            "requirement": RecencyRequirement.MANDATORY,
            "max_days": 1,
            "preferred_days": 1,
            "reason": "Financial data must be real-time",
        },
        SearchCategory.SPORTS: {
            "requirement": RecencyRequirement.MANDATORY,
            "max_days": 7,
            "preferred_days": 1,
            "reason": "Sports scores and news are time-sensitive",
        },
        SearchCategory.TECH_DOCS: {
            "requirement": RecencyRequirement.RECOMMENDED,
            "max_days": 180,
            "preferred_days": 30,
            "reason": "Documentation updates but not as frequently",
        },
        SearchCategory.TUTORIALS: {
            "requirement": RecencyRequirement.RECOMMENDED,
            "max_days": 365,
            "preferred_days": 90,
            "reason": "Tutorials remain relevant but best practices evolve",
        },
        SearchCategory.SHOPPING: {
            "requirement": RecencyRequirement.RECOMMENDED,
            "max_days": 30,
            "preferred_days": 7,
            "reason": "Product information and prices change",
        },
        SearchCategory.HISTORICAL: {
            "requirement": RecencyRequirement.FORBIDDEN,
            "max_days": None,
            "preferred_days": None,
            "reason": "Historical facts do not change",
        },
        SearchCategory.GENERAL: {
            "requirement": RecencyRequirement.RECOMMENDED,
            "max_days": 30,
            "preferred_days": 7,
            "reason": "General queries benefit from recent information",
        },
    }

    @classmethod
    def get_policy(cls, category: SearchCategory) -> Dict[str, Any]:
        """Get policy for category"""
        return cls.POLICIES.get(category, cls.POLICIES[SearchCategory.GENERAL])

    @classmethod
    def enforce_recency(
        cls,
        category: SearchCategory,
        requested_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Enforce recency policy
        
        Args:
            category: Search category
            requested_days: Requested recency in days (if any)
            
        Returns:
            Enforced policy decision
        """
        policy = cls.get_policy(category)
        requirement = policy["requirement"]

        decision = {
            "category": category.value,
            "requirement": requirement.value,
            "enforced": False,
            "recency_days": None,
            "reason": policy["reason"],
        }

        if requirement == RecencyRequirement.MANDATORY:
            # MUST use recency
            if requested_days is None or requested_days > policy["max_days"]:
                # Override with preferred
                decision["recency_days"] = policy["preferred_days"]
                decision["enforced"] = True
                decision["enforcement_reason"] = (
                    f"Category '{category.value}' requires recency. "
                    f"Using {policy['preferred_days']} days."
                )
            else:
                decision["recency_days"] = requested_days

        elif requirement == RecencyRequirement.RECOMMENDED:
            # Should use recency but can be overridden with reason
            decision["recency_days"] = requested_days or policy["preferred_days"]

        elif requirement == RecencyRequirement.FORBIDDEN:
            # Must NOT use recency
            decision["recency_days"] = None
            if requested_days:
                decision["enforced"] = True
                decision["enforcement_reason"] = (
                    f"Category '{category.value}' forbids recency filters. "
                    f"Searching all time."
                )

        else:  # OPTIONAL
            decision["recency_days"] = requested_days

        logger.info(
            "Recency policy enforced",
            category=category.value,
            requirement=requirement.value,
            final_days=decision["recency_days"],
            enforced=decision["enforced"],
        )

        return decision

    @classmethod
    def validate_override(
        cls,
        category: SearchCategory,
        override_days: Optional[int],
        reason: str,
    ) -> bool:
        """
        Validate if LLM can override policy
        
        Args:
            category: Search category
            override_days: Requested override
            reason: Reason for override
            
        Returns:
            True if override is allowed
        """
        policy = cls.get_policy(category)
        requirement = policy["requirement"]

        # Mandatory policies cannot be overridden
        if requirement == RecencyRequirement.MANDATORY:
            logger.warning(
                "Override rejected - mandatory policy",
                category=category.value,
                reason=reason,
            )
            return False

        # Forbidden policies cannot be overridden
        if requirement == RecencyRequirement.FORBIDDEN:
            if override_days is not None:
                logger.warning(
                    "Override rejected - forbidden policy",
                    category=category.value,
                    reason=reason,
                )
                return False

        # Recommended policies can be overridden with good reason
        if requirement == RecencyRequirement.RECOMMENDED:
            if len(reason) < 20:
                logger.warning(
                    "Override rejected - insufficient reason",
                    category=category.value,
                    reason=reason,
                )
                return False
            
            logger.info(
                "Override allowed",
                category=category.value,
                override_days=override_days,
                reason=reason,
            )
            return True

        # Optional policies can always be overridden
        return True


class PreClassifier:
    """
    Pre-classifier for quick search categorization.
    
    This runs BEFORE LLM to enforce policies early.
    """

    # Keyword patterns for each category
    PATTERNS = {
        SearchCategory.NEWS: [
            "новости", "news", "сегодня", "вчера", "today", "yesterday",
            "случилось", "happened", "events",
        ],
        SearchCategory.TECH_NEWS: [
            "ai news", "tech news", "новости технологий", "новости ai",
            "выпустили", "released", "анонс", "announcement",
        ],
        SearchCategory.WEATHER: [
            "погода", "weather", "температура", "temperature", "прогноз", "forecast",
            "дождь", "rain", "снег", "snow",
        ],
        SearchCategory.TRANSPORT: [
            "расписание", "schedule", "поезд", "train", "электричка", "suburban",
            "автобус", "bus", "рейс", "flight",
        ],
        SearchCategory.STOCKS: [
            "курс", "rate", "акции", "stocks", "биржа", "exchange",
            "цена акции", "stock price", "котировки", "quotes",
        ],
        SearchCategory.SPORTS: [
            "счёт", "score", "матч", "match", "игра", "game",
            "чемпионат", "championship", "турнир", "tournament",
        ],
        SearchCategory.TECH_DOCS: [
            "документация", "documentation", "api", "docs",
            "reference", "specification",
        ],
        SearchCategory.TUTORIALS: [
            "как", "how to", "инструкция", "tutorial", "guide",
            "научиться", "learn", "пошагово", "step by step",
        ],
        SearchCategory.SHOPPING: [
            "купить", "buy", "цена", "price", "стоимость", "cost",
            "магазин", "shop", "заказать", "order",
        ],
        SearchCategory.HISTORICAL: [
            "история", "historical", "когда был", "when was",
            "в каком году", "what year", "кто был", "who was",
            "биография", "biography",
        ],
    }

    @classmethod
    def classify(cls, query: str) -> SearchCategory:
        """
        Classify query into category
        
        Args:
            query: Search query
            
        Returns:
            Search category
        """
        query_lower = query.lower()

        # Check each category's patterns
        for category, patterns in cls.PATTERNS.items():
            if any(pattern in query_lower for pattern in patterns):
                logger.info("Pre-classified query", query=query[:50], category=category.value)
                return category

        # Default to general
        logger.info("Pre-classified as general", query=query[:50])
        return SearchCategory.GENERAL


# Singleton instances
recency_policy = RecencyPolicy()
pre_classifier = PreClassifier()
