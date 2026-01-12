"""Text-based agent using OpenAI Chat Completions API"""

import json
import time
from typing import Dict, List, Optional, Any, AsyncGenerator
from openai import AsyncOpenAI, OpenAIError
from app.agents.base import (
    BaseAgent,
    AgentType,
    AgentContext,
    AgentResponse,
    ResponseType,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TextAgent(BaseAgent):
    """
    Text-based LLM agent using OpenAI Chat Completions.
    
    Features:
    - Traditional chat completions (non-streaming and streaming)
    - Function/tool calling support
    - Structured output parsing
    - Context management
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        super().__init__(AgentType.TEXT)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client: Optional[AsyncOpenAI] = None

    async def initialize(self) -> None:
        """Initialize OpenAI client"""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        logger.info(
            "Text agent initialized",
            model=self.model,
            temperature=self.temperature,
        )

    async def shutdown(self) -> None:
        """Cleanup resources"""
        if self.client:
            await self.client.close()
            self.client = None
        logger.info("Text agent shutdown")

    async def process(
        self,
        context: AgentContext,
        input_text: Optional[str] = None,
        input_audio: Optional[bytes] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentResponse:
        """
        Process text input through Chat Completions API
        
        Args:
            context: Agent context
            input_text: Text input
            input_audio: Not used for text agent
            tools: Optional tools for function calling
            
        Returns:
            Agent response
        """
        if not self.client:
            raise RuntimeError("Agent not initialized. Call initialize() first.")

        if not input_text:
            raise ValueError("Text input is required for TextAgent")

        start_time = time.time()

        # Build messages from context
        messages = self._build_messages(context, input_text)

        try:
            # Call OpenAI
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**request_params)

            choice = response.choices[0]
            message = choice.message

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Handle tool calls
            if message.tool_calls:
                return AgentResponse(
                    type=ResponseType.FUNCTION_CALL,
                    content=message.content or "",
                    metadata={
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "function": tc.function.name,
                                "arguments": json.loads(tc.function.arguments),
                            }
                            for tc in message.tool_calls
                        ],
                        "finish_reason": choice.finish_reason,
                    },
                    tokens_used=response.usage.total_tokens if response.usage else None,
                    latency_ms=latency_ms,
                )

            # Regular text response
            content = message.content or ""

            # Try to parse as JSON action plan
            response_type = ResponseType.TEXT
            actions = None
            needs_confirmation = False

            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "intent" in parsed:
                    response_type = ResponseType.ACTION_PLAN
                    actions = parsed.get("actions", [])
                    needs_confirmation = parsed.get("needs_confirmation", False)
                    content = parsed.get("response", content)
            except json.JSONDecodeError:
                # Not JSON, keep as text
                pass

            # Add to context
            self.add_message(context, "assistant", content)

            logger.info(
                "Text agent processed",
                user_id=context.user_id,
                response_type=response_type.value,
                tokens=response.usage.total_tokens if response.usage else 0,
                latency_ms=latency_ms,
            )

            return AgentResponse(
                type=response_type,
                content=content,
                actions=actions,
                needs_confirmation=needs_confirmation,
                tokens_used=response.usage.total_tokens if response.usage else None,
                latency_ms=latency_ms,
                metadata={
                    "finish_reason": choice.finish_reason,
                    "model": self.model,
                },
            )

        except OpenAIError as e:
            logger.error("OpenAI API error", error=str(e), user_id=context.user_id)
            raise

        except Exception as e:
            logger.error(
                "Text agent processing failed",
                error=str(e),
                user_id=context.user_id,
            )
            raise

    async def stream_process(
        self,
        context: AgentContext,
        input_text: Optional[str] = None,
        input_audio: Optional[bytes] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[AgentResponse, None]:
        """
        Stream text responses
        
        Args:
            context: Agent context
            input_text: Text input
            input_audio: Not used
            tools: Optional tools
            
        Yields:
            Partial responses
        """
        if not self.client:
            raise RuntimeError("Agent not initialized")

        if not input_text:
            raise ValueError("Text input is required")

        start_time = time.time()
        messages = self._build_messages(context, input_text)

        try:
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }

            if tools:
                request_params["tools"] = tools

            stream = await self.client.chat.completions.create(**request_params)

            accumulated_content = ""
            
            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                
                if delta.content:
                    accumulated_content += delta.content
                    
                    yield AgentResponse(
                        type=ResponseType.STREAM,
                        content=delta.content,
                        metadata={
                            "accumulated": accumulated_content,
                            "finish_reason": chunk.choices[0].finish_reason,
                        },
                        latency_ms=(time.time() - start_time) * 1000,
                    )

            # Add final message to context
            if accumulated_content:
                self.add_message(context, "assistant", accumulated_content)

            logger.info(
                "Text agent stream completed",
                user_id=context.user_id,
                content_length=len(accumulated_content),
            )

        except Exception as e:
            logger.error("Stream processing failed", error=str(e))
            raise

    def _build_messages(
        self,
        context: AgentContext,
        current_input: str,
    ) -> List[Dict[str, Any]]:
        """
        Build messages array for OpenAI API
        
        Args:
            context: Agent context
            current_input: Current user input
            
        Returns:
            List of message dictionaries
        """
        messages = []

        # System message with context
        system_content = self._build_system_prompt(context)
        messages.append({"role": "system", "content": system_content})

        # Recent conversation history (last 10 messages)
        for msg in context.messages[-10:]:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Current input
        user_message = self._build_user_message(context, current_input)
        messages.append({"role": "user", "content": user_message})

        # Add to context
        self.add_message(context, "user", current_input)

        return messages

    def _build_system_prompt(self, context: AgentContext) -> str:
        """Build system prompt with context"""
        prompt_parts = [
            f"Ты — {settings.assistant_name}, умный голосовой ассистент для управления домом через Home Assistant.",
            f"Стиль: {', '.join(settings.assistant_style_list)}",
            f"Язык: {settings.assistant_language}",
            "",
            "Твои задачи:",
            "1. Понимать естественные команды пользователя",
            "2. Планировать действия в Home Assistant",
            "3. Учитывать контекст и предпочтения пользователя",
            "4. Запрашивать подтверждение для опасных действий",
            "",
            "Для управления домом возвращай JSON:",
            '{"intent": "...", "actions": [...], "needs_confirmation": true/false, "response": "..."}',
            "",
            "ВАЖНО:",
            "- НЕ выдумывай entity_id! Используй только те, что есть в контексте",
            "- Опасные действия требуют подтверждения",
            "- Для обычных вопросов возвращай текст",
        ]

        # Add user rules if present
        if context.user_rules:
            prompt_parts.append("")
            prompt_parts.append("Правила пользователя:")
            for rule in context.user_rules[:5]:
                prompt_parts.append(f"- {rule.get('rule_text', '')}")

        return "\n".join(prompt_parts)

    def _build_user_message(
        self,
        context: AgentContext,
        input_text: str,
    ) -> str:
        """Build user message with context"""
        parts = []

        # HA context summary
        if context.ha_context:
            ha_ctx = context.ha_context
            parts.append("Контекст Home Assistant:")
            parts.append(f"- Устройств: {ha_ctx.get('total_entities', 0)}")
            
            if ha_ctx.get("areas"):
                parts.append(f"- Комнат: {len(ha_ctx['areas'])}")

        # Relevant memories
        if context.relevant_memories:
            parts.append("")
            parts.append("Из истории:")
            for memory in context.relevant_memories[:2]:
                parts.append(f"- {memory.get('content', '')[:100]}")

        # Current command
        parts.append("")
        parts.append(f"Команда: {input_text}")

        return "\n".join(parts)

    async def health_check(self) -> Dict[str, Any]:
        """Check agent health"""
        healthy = self.client is not None
        
        if healthy:
            try:
                # Simple test call
                await self.client.models.list()
            except Exception as e:
                healthy = False
                logger.error("Text agent health check failed", error=str(e))

        return {
            "agent_type": self.agent_type.value,
            "model": self.model,
            "healthy": healthy,
            "active_sessions": len(self.active_sessions),
        }
