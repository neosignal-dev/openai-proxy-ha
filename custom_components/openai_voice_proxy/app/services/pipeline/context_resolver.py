"""Context resolver - gathers all required context for execution"""

from typing import Dict, Any, Optional
from app.core.logging import get_logger
from app.integrations.homeassistant import ha_client
from app.services.memory import memory_service

logger = get_logger(__name__)


class ContextResolver:
    """
    Resolves and builds complete context for command execution.
    
    Responsibilities:
    - Fetch HA context (entities, states, areas)
    - Retrieve relevant memories
    - Get user rules and preferences
    - Build unified context structure
    - Cache context when appropriate
    """

    def __init__(self):
        self.context_cache: Dict[str, Dict[str, Any]] = {}

    async def resolve(
        self,
        user_id: str,
        command: str,
        intent: Dict[str, Any],
        include_ha: bool = False,
        include_memory: bool = False,
    ) -> Dict[str, Any]:
        """
        Resolve complete context
        
        Args:
            user_id: User identifier
            command: User command
            intent: Intent analysis result
            include_ha: Include Home Assistant context
            include_memory: Include memory context
            
        Returns:
            Complete context dictionary
        """
        logger.info(
            "Resolving context",
            user_id=user_id,
            include_ha=include_ha,
            include_memory=include_memory,
        )

        context = {
            "user_id": user_id,
            "command": command,
            "intent": intent,
        }

        # Home Assistant context
        if include_ha:
            ha_context = await self._get_ha_context(user_id)
            context["ha"] = ha_context

        # Memory context
        if include_memory:
            memory_context = await self._get_memory_context(user_id, command)
            context["memory"] = memory_context

        logger.info(
            "Context resolved",
            user_id=user_id,
            ha_entities=context.get("ha", {}).get("total_entities", 0),
            relevant_memories=len(context.get("memory", {}).get("relevant_memories", [])),
            user_rules=len(context.get("memory", {}).get("user_rules", [])),
        )

        return context

    async def _get_ha_context(
        self,
        user_id: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Get Home Assistant context
        
        Args:
            user_id: User identifier
            use_cache: Use cached context if available
            
        Returns:
            HA context dictionary
        """
        # Check cache (5 seconds TTL)
        cache_key = f"ha_context:{user_id}"
        if use_cache and cache_key in self.context_cache:
            cached = self.context_cache[cache_key]
            import time
            if time.time() - cached["timestamp"] < 5:
                logger.debug("Using cached HA context", user_id=user_id)
                return cached["data"]

        try:
            # Fetch from HA
            ha_context = await ha_client.get_context()
            
            # Cache it
            import time
            self.context_cache[cache_key] = {
                "data": ha_context,
                "timestamp": time.time(),
            }

            return ha_context

        except Exception as e:
            logger.error("Failed to get HA context", error=str(e))
            return {
                "config": {},
                "total_entities": 0,
                "areas": [],
                "entities_by_domain": {},
                "entities_by_area": {},
                "error": str(e),
            }

    async def _get_memory_context(
        self,
        user_id: str,
        command: str,
    ) -> Dict[str, Any]:
        """
        Get memory context
        
        Args:
            user_id: User identifier
            command: User command
            
        Returns:
            Memory context dictionary
        """
        try:
            # Get recent history
            recent_history = await memory_service.get_short_term_history(user_id, limit=10)

            # Search relevant long-term memories
            relevant_memories = await memory_service.search_long_term(user_id, command, limit=3)

            # Get user rules
            user_rules = await memory_service.get_user_rules(user_id)

            # Search relevant rules
            relevant_rules = await memory_service.search_relevant_rules(user_id, command, limit=3)

            return {
                "recent_history": recent_history,
                "relevant_memories": relevant_memories,
                "user_rules": user_rules,
                "relevant_rules": relevant_rules,
            }

        except Exception as e:
            logger.error("Failed to get memory context", error=str(e))
            return {
                "recent_history": [],
                "relevant_memories": [],
                "user_rules": [],
                "relevant_rules": [],
                "error": str(e),
            }

    def extract_entities_from_ha(
        self,
        ha_context: Dict[str, Any],
        domain: Optional[str] = None,
        area: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """
        Extract specific entities from HA context
        
        Args:
            ha_context: HA context dictionary
            domain: Optional domain filter (light, switch, etc.)
            area: Optional area filter
            
        Returns:
            List of matching entities
        """
        entities = []

        if domain:
            domain_entities = ha_context.get("entities_by_domain", {}).get(domain, [])
            entities.extend(domain_entities)
        
        if area:
            area_entities = ha_context.get("entities_by_area", {}).get(area, [])
            entities.extend(area_entities)

        return entities

    def format_context_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format context for LLM consumption
        
        Args:
            context: Complete context dictionary
            
        Returns:
            Formatted context string
        """
        parts = []

        # Intent
        intent = context.get("intent", {})
        parts.append(f"Намерение: {intent.get('type', 'unknown')}")

        # HA context
        ha_ctx = context.get("ha", {})
        if ha_ctx:
            parts.append(f"\nУстройств в Home Assistant: {ha_ctx.get('total_entities', 0)}")
            
            areas = ha_ctx.get("areas", [])
            if areas:
                parts.append(f"Комнаты: {', '.join(areas[:10])}")

        # User rules
        memory_ctx = context.get("memory", {})
        if memory_ctx:
            rules = memory_ctx.get("relevant_rules", [])
            if rules:
                parts.append("\nПравила пользователя:")
                for rule in rules[:3]:
                    parts.append(f"- {rule.get('rule_text', '')}")

            # Relevant memories
            memories = memory_ctx.get("relevant_memories", [])
            if memories:
                parts.append("\nИз истории:")
                for memory in memories[:2]:
                    parts.append(f"- {memory.get('content', '')[:100]}")

        return "\n".join(parts)


# Global instance
context_resolver = ContextResolver()
