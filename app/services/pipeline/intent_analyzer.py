"""Intent analyzer - determines what the user wants to do"""

from typing import Dict, Any, Optional
from enum import Enum
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class IntentType(str, Enum):
    """Types of user intents"""
    # Home Assistant control
    HA_CONTROL = "ha_control"  # Control devices
    HA_QUERY = "ha_query"  # Query device states
    HA_AUTOMATION = "ha_automation"  # Create/modify automations
    
    # Information retrieval
    WEB_SEARCH = "web_search"  # Web search required
    HABR_SEARCH = "habr_search"  # Habr-specific search
    MEMORY_QUERY = "memory_query"  # Query past conversations
    
    # User preferences
    SET_RULE = "set_rule"  # Set user preference/rule
    
    # General conversation
    GENERAL_CHAT = "general_chat"  # General conversation
    
    # Unknown
    UNKNOWN = "unknown"


class IntentAnalyzer:
    """
    Analyzes user input to determine intent.
    
    Responsibilities:
    - Classify user intent into categories
    - Extract key entities (devices, locations, times)
    - Determine required resources (HA, search, memory)
    - Pre-filter obvious cases without LLM
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Keywords for quick classification
        self.ha_keywords = [
            "включи", "выключи", "открой", "закрой", "установи", "запусти",
            "turn on", "turn off", "open", "close", "set", "start", "stop",
        ]
        
        self.search_keywords = [
            "найди", "поищи", "погугли", "что такое", "кто такой", "расскажи о",
            "search", "find", "google", "what is", "who is", "tell me about",
        ]
        
        self.habr_keywords = [
            "habr", "хабр", "статья", "article",
        ]
        
        self.memory_keywords = [
            "помнишь", "вспомни", "когда я", "в прошлый раз",
            "remember", "recall", "last time",
        ]

    async def analyze(
        self,
        user_id: str,
        command: str,
        quick_classify: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze user intent
        
        Args:
            user_id: User identifier
            command: User command
            quick_classify: Use quick keyword-based classification first
            
        Returns:
            Intent analysis result
        """
        logger.info("Analyzing intent", user_id=user_id, command=command[:50])

        # Quick classification (no LLM)
        if quick_classify:
            quick_intent = self._quick_classify(command)
            if quick_intent:
                logger.info("Quick intent classification", intent=quick_intent["type"])
                return quick_intent

        # LLM-based classification for complex cases
        return await self._llm_classify(user_id, command)

    def _quick_classify(self, command: str) -> Optional[Dict[str, Any]]:
        """
        Quick keyword-based classification
        
        Args:
            command: User command
            
        Returns:
            Intent dict or None if classification not confident
        """
        command_lower = command.lower()

        # Habr search (very specific)
        if any(kw in command_lower for kw in self.habr_keywords):
            return {
                "type": IntentType.HABR_SEARCH,
                "confidence": 0.95,
                "entities": {},
                "requires": ["habr"],
            }

        # Memory query
        if any(kw in command_lower for kw in self.memory_keywords):
            return {
                "type": IntentType.MEMORY_QUERY,
                "confidence": 0.90,
                "entities": {},
                "requires": ["memory"],
            }

        # Web search (general questions)
        if any(kw in command_lower for kw in self.search_keywords):
            return {
                "type": IntentType.WEB_SEARCH,
                "confidence": 0.85,
                "entities": {},
                "requires": ["perplexity"],
            }

        # HA control (has action keywords)
        if any(kw in command_lower for kw in self.ha_keywords):
            return {
                "type": IntentType.HA_CONTROL,
                "confidence": 0.80,
                "entities": {},
                "requires": ["homeassistant", "memory"],
            }

        # Not confident enough
        return None

    async def _llm_classify(
        self,
        user_id: str,
        command: str,
    ) -> Dict[str, Any]:
        """
        LLM-based intent classification
        
        Args:
            user_id: User identifier
            command: User command
            
        Returns:
            Intent analysis result
        """
        system_prompt = f"""Ты — классификатор намерений пользователя для умного дома.

Доступные типы намерений:
- ha_control: Управление устройствами (включи свет, открой штору)
- ha_query: Запрос состояния (какая температура, горит ли свет)
- ha_automation: Создание автоматизаций (создай правило, автоматизируй)
- web_search: Поиск в интернете (найди информацию, что такое)
- habr_search: Поиск на Хабре (найди статью на Хабре)
- memory_query: Запрос из истории (помнишь, вспомни)
- set_rule: Установка правила (запомни, всегда)
- general_chat: Обычный разговор (привет, как дела, расскажи анекдот)

Верни JSON:
{{
  "type": "intent_type",
  "confidence": 0.95,
  "entities": {{"key": "value"}},
  "requires": ["resource1", "resource2"]
}}

Возможные resources: homeassistant, perplexity, habr, memory, none"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for speed
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command},
                ],
                temperature=0.1,
                max_tokens=200,
            )

            content = response.choices[0].message.content
            
            # Parse JSON response
            import json
            intent = json.loads(content)
            
            logger.info(
                "LLM intent classification",
                user_id=user_id,
                intent_type=intent["type"],
                confidence=intent["confidence"],
            )

            return intent

        except Exception as e:
            logger.error("Intent classification failed", error=str(e))
            # Fallback to general chat
            return {
                "type": IntentType.GENERAL_CHAT,
                "confidence": 0.5,
                "entities": {},
                "requires": ["none"],
            }

    def should_use_search(self, intent: Dict[str, Any]) -> bool:
        """Check if search is required"""
        return intent["type"] in [
            IntentType.WEB_SEARCH,
            IntentType.HABR_SEARCH,
        ]

    def should_use_ha(self, intent: Dict[str, Any]) -> bool:
        """Check if HA is required"""
        return intent["type"] in [
            IntentType.HA_CONTROL,
            IntentType.HA_QUERY,
            IntentType.HA_AUTOMATION,
        ]

    def should_use_memory(self, intent: Dict[str, Any]) -> bool:
        """Check if memory is required"""
        return intent["type"] in [
            IntentType.MEMORY_QUERY,
            IntentType.HA_CONTROL,  # For preferences
            IntentType.HA_QUERY,
        ]


# Global instance
intent_analyzer = IntentAnalyzer()
