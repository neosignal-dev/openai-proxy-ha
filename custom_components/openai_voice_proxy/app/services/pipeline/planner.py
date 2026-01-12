"""Planner - generates action plans based on intent and context"""

import json
from typing import Dict, Any, List, Optional
from app.agents.text_agent import TextAgent
from app.agents.base import AgentContext, AgentMessage
from app.services.pipeline.intent_analyzer import IntentType
from app.integrations.perplexity import perplexity_client
from app.integrations.habr import habr_client
from app.core.logging import get_logger

logger = get_logger(__name__)


class Planner:
    """
    Generates executable action plans.
    
    Responsibilities:
    - Use LLM to generate action plans for HA control
    - Handle web searches (Perplexity/Habr)
    - Generate responses for general chat
    - Validate plans before execution
    - Determine if confirmation is needed
    """

    def __init__(self):
        self.text_agent = TextAgent()

    async def initialize(self) -> None:
        """Initialize planner resources"""
        await self.text_agent.initialize()
        logger.info("Planner initialized")

    async def shutdown(self) -> None:
        """Cleanup planner resources"""
        await self.text_agent.shutdown()
        logger.info("Planner shutdown")

    async def plan(
        self,
        user_id: str,
        command: str,
        intent: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate action plan
        
        Args:
            user_id: User identifier
            command: User command
            intent: Intent analysis
            context: Resolved context
            
        Returns:
            Action plan dictionary
        """
        intent_type = intent.get("type")

        logger.info(
            "Planning action",
            user_id=user_id,
            intent_type=intent_type,
        )

        # Route to appropriate planner
        if intent_type == IntentType.HA_CONTROL:
            return await self._plan_ha_control(user_id, command, context)
        
        elif intent_type == IntentType.HA_QUERY:
            return await self._plan_ha_query(user_id, command, context)
        
        elif intent_type == IntentType.WEB_SEARCH:
            return await self._plan_web_search(user_id, command, context)
        
        elif intent_type == IntentType.HABR_SEARCH:
            return await self._plan_habr_search(user_id, command, context)
        
        elif intent_type == IntentType.HA_AUTOMATION:
            return await self._plan_automation(user_id, command, context)
        
        elif intent_type == IntentType.SET_RULE:
            return await self._plan_set_rule(user_id, command, context)
        
        elif intent_type == IntentType.MEMORY_QUERY:
            return await self._plan_memory_query(user_id, command, context)
        
        else:  # GENERAL_CHAT or UNKNOWN
            return await self._plan_general_chat(user_id, command, context)

    async def _plan_ha_control(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan Home Assistant control actions"""
        
        # Build agent context
        agent_context = self._build_agent_context(user_id, context)

        # Use text agent to generate plan
        response = await self.text_agent.process(
            context=agent_context,
            input_text=command,
        )

        # Parse action plan
        if response.actions:
            return {
                "type": "action_plan",
                "intent": "ha_control",
                "actions": response.actions,
                "needs_confirmation": response.needs_confirmation,
                "response_text": response.content,
            }
        else:
            return {
                "type": "text_response",
                "intent": "ha_control",
                "response_text": response.content,
            }

    async def _plan_ha_query(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan Home Assistant query"""
        
        agent_context = self._build_agent_context(user_id, context)
        
        response = await self.text_agent.process(
            context=agent_context,
            input_text=command,
        )

        return {
            "type": "text_response",
            "intent": "ha_query",
            "response_text": response.content,
        }

    async def _plan_web_search(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan web search using Perplexity"""
        
        try:
            # Perform search
            search_result = await perplexity_client.search(
                query=command,
                max_results=5,
            )

            return {
                "type": "search_response",
                "intent": "web_search",
                "search_provider": "perplexity",
                "answer": search_result["answer"],
                "sources": search_result["sources"],
                "response_text": search_result["answer"],
            }

        except Exception as e:
            logger.error("Web search failed", error=str(e))
            return {
                "type": "error_response",
                "intent": "web_search",
                "error": str(e),
                "response_text": f"Не удалось выполнить поиск: {str(e)}",
            }

    async def _plan_habr_search(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan Habr search"""
        
        try:
            # Extract query (remove "habr" keyword)
            query = command.lower().replace("habr", "").replace("хабр", "").strip()
            
            # Perform search
            articles = await habr_client.search(
                query=query if query else None,
                limit=5,
            )

            # Format response
            if articles:
                response_parts = ["Нашёл статьи на Хабре:"]
                for i, article in enumerate(articles[:3], 1):
                    response_parts.append(
                        f"{i}. {article['title']} - {article.get('stats', {}).get('views', 0)} просмотров"
                    )
                response_text = "\n".join(response_parts)
            else:
                response_text = "Статьи не найдены"

            return {
                "type": "search_response",
                "intent": "habr_search",
                "search_provider": "habr",
                "articles": articles,
                "response_text": response_text,
            }

        except Exception as e:
            logger.error("Habr search failed", error=str(e))
            return {
                "type": "error_response",
                "intent": "habr_search",
                "error": str(e),
                "response_text": f"Не удалось найти статьи: {str(e)}",
            }

    async def _plan_automation(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan automation creation"""
        
        agent_context = self._build_agent_context(user_id, context)
        
        # Add automation creation instructions
        automation_prompt = (
            f"{command}\n\n"
            "Создай черновик автоматизации для Home Assistant в формате YAML."
        )
        
        response = await self.text_agent.process(
            context=agent_context,
            input_text=automation_prompt,
        )

        return {
            "type": "automation_draft",
            "intent": "ha_automation",
            "draft": response.content,
            "response_text": "Создал черновик автоматизации. Проверьте перед применением.",
        }

    async def _plan_set_rule(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan setting user rule"""
        
        # Extract rule from command
        rule_text = command
        
        # Remove common prefixes
        for prefix in ["запомни", "всегда", "помни", "правило"]:
            rule_text = rule_text.lower().replace(prefix, "").strip()

        return {
            "type": "set_rule",
            "intent": "set_rule",
            "rule_text": rule_text,
            "rule_type": "preference",
            "response_text": f"Запомнил: {rule_text}",
        }

    async def _plan_memory_query(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan memory query"""
        
        memory_ctx = context.get("memory", {})
        relevant_memories = memory_ctx.get("relevant_memories", [])

        if relevant_memories:
            # Build response from memories
            response_parts = ["Из истории наших разговоров:"]
            for memory in relevant_memories[:3]:
                response_parts.append(f"- {memory.get('content', '')[:200]}")
            
            response_text = "\n".join(response_parts)
        else:
            response_text = "Не нашёл ничего в истории по этому запросу"

        return {
            "type": "memory_response",
            "intent": "memory_query",
            "memories": relevant_memories,
            "response_text": response_text,
        }

    async def _plan_general_chat(
        self,
        user_id: str,
        command: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Plan general conversation response"""
        
        agent_context = self._build_agent_context(user_id, context)
        
        response = await self.text_agent.process(
            context=agent_context,
            input_text=command,
        )

        return {
            "type": "text_response",
            "intent": "general_chat",
            "response_text": response.content,
        }

    def _build_agent_context(
        self,
        user_id: str,
        context: Dict[str, Any],
    ) -> AgentContext:
        """Build agent context from pipeline context"""
        
        agent_context = AgentContext(user_id=user_id)

        # Add HA context
        ha_ctx = context.get("ha", {})
        if ha_ctx:
            agent_context.ha_context = ha_ctx

        # Add user rules
        memory_ctx = context.get("memory", {})
        if memory_ctx:
            agent_context.user_rules = memory_ctx.get("relevant_rules", [])
            agent_context.relevant_memories = memory_ctx.get("relevant_memories", [])

            # Add recent history to messages
            for msg in memory_ctx.get("recent_history", []):
                agent_context.messages.append(
                    AgentMessage(
                        role=msg["role"],
                        content=msg["content"],
                        metadata=msg.get("metadata", {}),
                    )
                )

        return agent_context


# Global instance
planner = Planner()
