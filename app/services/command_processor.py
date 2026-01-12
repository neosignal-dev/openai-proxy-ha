"""Command processing and LLM planning service"""

import json
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import ActionLog, async_session_maker
from app.integrations.homeassistant import ha_client
from app.services.memory import memory_service

logger = get_logger(__name__)


SYSTEM_PROMPT = """Ты — {assistant_name}, умный голосовой ассистент для управления домом через Home Assistant.

Твои характеристики:
- Стиль: {style}
- Язык: {language}
- Отвечай кратко, по делу, дружелюбно

Твои задачи:
1. Понимать естественные команды пользователя
2. Планировать действия в Home Assistant
3. Учитывать контекст и предпочтения пользователя
4. Запрашивать подтверждение для опасных действий

Когда получаешь команду для управления домом, возвращай СТРОГО JSON в формате:
{{
  "intent": "название_намерения",
  "actions": [
    {{
      "domain": "domain_name",
      "service": "service_name",
      "target": {{"entity_id": "entity.id" или "area_id": "area"}},
      "service_data": {{дополнительные параметры}}
    }}
  ],
  "needs_confirmation": true/false,
  "response": "Текстовый ответ пользователю"
}}

ВАЖНО:
- НЕ выдумывай entity_id! Используй только те, что есть в контексте
- Если данных недостаточно — запроси у пользователя
- Опасные действия (замки, сигнализация, шторы) требуют подтверждения
- Для обычных вопросов (не управления домом) возвращай просто текстовый ответ

Примеры:
Пользователь: "Включи свет в спальне"
Ответ: {{"intent": "lights_on", "actions": [{{"domain": "light", "service": "turn_on", "target": {{"area_id": "bedroom"}}}}], "needs_confirmation": false, "response": "Включаю свет в спальне"}}

Пользователь: "Расскажи анекдот"
Ответ: "Конечно! Вот анекдот: ..."
"""


class CommandProcessor:
    """Service for processing user commands and planning actions"""

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"  # Use GPT-4 for better reasoning

    async def process_command(
        self,
        user_id: str,
        command: str,
        ha_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process user command and generate action plan
        
        Args:
            user_id: User identifier
            command: User command
            ha_context: Optional Home Assistant context
            
        Returns:
            Action plan or text response
        """
        logger.info("Processing command", user_id=user_id, command=command)

        # Build context
        context = await memory_service.build_context(
            user_id=user_id,
            current_query=command,
            ha_context=ha_context,
        )

        # Build system prompt
        system_prompt = SYSTEM_PROMPT.format(
            assistant_name=settings.assistant_name,
            style=", ".join(settings.assistant_style_list),
            language=settings.assistant_language,
        )

        # Build context for LLM
        context_text = self._format_context(context)

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add recent history
        for msg in context["recent_history"][-5:]:  # Last 5 messages
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # Add current command with context
        user_message = f"Контекст:\n{context_text}\n\nКоманда пользователя: {command}"
        messages.append({"role": "user", "content": user_message})

        # Call OpenAI
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )

            assistant_response = response.choices[0].message.content

            # Try to parse as JSON (action plan)
            try:
                action_plan = json.loads(assistant_response)
                if isinstance(action_plan, dict) and "intent" in action_plan:
                    # Validate action plan
                    validated_plan = await self._validate_action_plan(action_plan, ha_context)
                    
                    # Save to memory
                    await memory_service.add_to_short_term(
                        user_id=user_id,
                        role="user",
                        content=command,
                    )
                    await memory_service.add_to_short_term(
                        user_id=user_id,
                        role="assistant",
                        content=validated_plan.get("response", ""),
                    )

                    return validated_plan
            except json.JSONDecodeError:
                # Not JSON, it's a text response
                pass

            # Text response
            await memory_service.add_to_short_term(
                user_id=user_id,
                role="user",
                content=command,
            )
            await memory_service.add_to_short_term(
                user_id=user_id,
                role="assistant",
                content=assistant_response,
            )

            return {
                "type": "text_response",
                "response": assistant_response,
            }

        except Exception as e:
            logger.error("Command processing failed", error=str(e))
            raise

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for LLM
        
        Args:
            context: Context dictionary
            
        Returns:
            Formatted context string
        """
        parts = []

        # Relevant rules
        if context["relevant_rules"]:
            parts.append("Правила и предпочтения пользователя:")
            for rule in context["relevant_rules"]:
                parts.append(f"- {rule['rule_text']}")

        # HA context summary
        ha_ctx = context.get("ha_context", {})
        if ha_ctx:
            parts.append(f"\nДоступно устройств: {ha_ctx.get('total_entities', 0)}")
            
            if ha_ctx.get("entities_by_area"):
                parts.append("Комнаты:")
                for area, entities in list(ha_ctx["entities_by_area"].items())[:5]:
                    parts.append(f"- {area}: {len(entities)} устройств")

        # Relevant memories
        if context["relevant_memories"]:
            parts.append("\nИз истории:")
            for memory in context["relevant_memories"][:2]:
                parts.append(f"- {memory['content'][:100]}")

        return "\n".join(parts) if parts else "Контекст пуст"

    async def _validate_action_plan(
        self,
        plan: Dict[str, Any],
        ha_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validate and enrich action plan
        
        Args:
            plan: Action plan from LLM
            ha_context: Home Assistant context
            
        Returns:
            Validated action plan
        """
        validated_plan = plan.copy()

        # Validate each action
        validated_actions = []
        for action in plan.get("actions", []):
            domain = action.get("domain")
            service = action.get("service")
            
            if not domain or not service:
                logger.warning("Invalid action: missing domain or service", action=action)
                continue

            service_call = f"{domain}.{service}"

            # Check if service needs confirmation
            if ha_client.needs_confirmation(service_call):
                validated_plan["needs_confirmation"] = True

            validated_actions.append(action)

        validated_plan["actions"] = validated_actions

        return validated_plan

    async def execute_action_plan(
        self,
        user_id: str,
        plan: Dict[str, Any],
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Execute action plan
        
        Args:
            user_id: User identifier
            plan: Action plan to execute
            confirmed: Whether user has confirmed
            
        Returns:
            Execution result
        """
        intent = plan.get("intent", "unknown")
        actions = plan.get("actions", [])
        needs_confirmation = plan.get("needs_confirmation", False)

        logger.info(
            "Executing action plan",
            user_id=user_id,
            intent=intent,
            actions_count=len(actions),
            confirmed=confirmed,
        )

        # Check confirmation
        if needs_confirmation and not confirmed:
            return {
                "success": False,
                "needs_confirmation": True,
                "message": "Это действие требует подтверждения. Подтвердите выполнение.",
                "plan": plan,
            }

        # Execute actions
        results = []
        all_success = True
        error_message = None

        for action in actions:
            try:
                domain = action["domain"]
                service = action["service"]
                target = action.get("target", {})
                service_data = action.get("service_data", {})

                # Call HA service
                result = await ha_client.call_service(
                    domain=domain,
                    service=service,
                    service_data=service_data,
                    target=target,
                )

                results.append({
                    "action": action,
                    "success": True,
                    "result": result,
                })

                logger.info(
                    "Action executed",
                    domain=domain,
                    service=service,
                    affected_entities=len(result),
                )

            except Exception as e:
                logger.error("Action failed", action=action, error=str(e))
                all_success = False
                error_message = str(e)
                results.append({
                    "action": action,
                    "success": False,
                    "error": str(e),
                })

        # Log to database
        async with async_session_maker() as session:
            log_entry = ActionLog(
                user_id=user_id,
                intent=intent,
                actions=actions,
                confirmed=confirmed,
                executed=True,
                success=all_success,
                error=error_message,
            )
            session.add(log_entry)
            await session.commit()

        return {
            "success": all_success,
            "results": results,
            "message": "Действия выполнены" if all_success else f"Ошибка: {error_message}",
        }


# Global command processor instance
command_processor = CommandProcessor()


