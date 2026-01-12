"""Response composer - formats responses for different channels"""

from typing import Dict, Any, Optional
from app.services.tts.openai_tts import openai_tts
from app.services.tts.base import TTSRequest, TTSVoice, AudioFormat
from app.core.logging import get_logger

logger = get_logger(__name__)


class ResponseComposer:
    """
    Composes final responses for different output channels.
    
    Responsibilities:
    - Generate TTS audio for voice responses
    - Format text for different channels (voice, text, Telegram)
    - Handle streaming responses
    - Add metadata and context
    - Optimize response length for voice vs text
    """

    def __init__(self):
        self.tts = openai_tts

    async def initialize(self) -> None:
        """Initialize composer resources"""
        await self.tts.initialize()
        logger.info("Response composer initialized")

    async def shutdown(self) -> None:
        """Cleanup composer resources"""
        await self.tts.shutdown()
        logger.info("Response composer shutdown")

    async def compose(
        self,
        user_id: str,
        plan: Dict[str, Any],
        execution_result: Dict[str, Any],
        channel: str = "voice",  # voice, text, telegram
        include_audio: bool = True,
    ) -> Dict[str, Any]:
        """
        Compose final response
        
        Args:
            user_id: User identifier
            plan: Action plan
            execution_result: Execution result
            channel: Output channel
            include_audio: Whether to include TTS audio
            
        Returns:
            Complete response dictionary
        """
        logger.info(
            "Composing response",
            user_id=user_id,
            channel=channel,
            include_audio=include_audio,
        )

        # Get response text
        response_text = self._build_response_text(plan, execution_result, channel)

        # Build base response
        response = {
            "type": plan.get("type", "text_response"),
            "intent": plan.get("intent", "unknown"),
            "text": response_text,
            "channel": channel,
        }

        # Add execution details if present
        if execution_result:
            response["execution"] = {
                "success": execution_result.get("success", True),
                "executed": execution_result.get("executed", 0),
                "failed": execution_result.get("failed", 0),
            }

        # Add plan-specific data
        if plan.get("type") == "search_response":
            response["sources"] = plan.get("sources", [])
            response["articles"] = plan.get("articles", [])
        
        elif plan.get("type") == "action_plan":
            response["actions"] = plan.get("actions", [])
            response["needs_confirmation"] = plan.get("needs_confirmation", False)

        # Generate TTS audio for voice channel
        if channel == "voice" and include_audio and response_text:
            try:
                audio_response = await self._generate_audio(response_text)
                response["audio"] = audio_response
            except Exception as e:
                logger.error("Failed to generate audio", error=str(e))
                response["audio_error"] = str(e)

        logger.info(
            "Response composed",
            user_id=user_id,
            text_length=len(response_text),
            has_audio="audio" in response,
        )

        return response

    def _build_response_text(
        self,
        plan: Dict[str, Any],
        execution_result: Dict[str, Any],
        channel: str,
    ) -> str:
        """Build response text based on plan and execution"""
        
        # Get base response text from plan
        response_text = plan.get("response_text", "")

        # Add execution feedback if actions were executed
        if execution_result and execution_result.get("executed", 0) > 0:
            execution_message = execution_result.get("message", "")
            if execution_message:
                response_text = f"{response_text}\n{execution_message}"

        # Format for channel
        if channel == "voice":
            response_text = self._optimize_for_voice(response_text)
        elif channel == "telegram":
            response_text = self._format_for_telegram(response_text, plan)

        return response_text

    def _optimize_for_voice(self, text: str) -> str:
        """
        Optimize text for voice output
        
        - Remove markdown formatting
        - Shorten lists
        - Use natural language
        """
        # Remove markdown
        text = text.replace("**", "").replace("*", "")
        text = text.replace("#", "")
        
        # Limit line breaks
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        # Truncate very long texts
        if len(text) > 500:
            text = text[:500] + "... (продолжение в текстовом виде)"

        return text.strip()

    def _format_for_telegram(
        self,
        text: str,
        plan: Dict[str, Any],
    ) -> str:
        """Format text with Telegram markdown"""
        
        # Keep markdown formatting for Telegram
        formatted = text

        # Add sources as links for search responses
        if plan.get("type") == "search_response":
            sources = plan.get("sources", [])
            if sources:
                formatted += "\n\n**Источники:**"
                for i, source in enumerate(sources[:5], 1):
                    formatted += f"\n{i}. {source}"

        # Add article links for Habr responses
        if plan.get("type") == "search_response" and plan.get("search_provider") == "habr":
            articles = plan.get("articles", [])
            if articles:
                formatted += "\n\n**Статьи:**"
                for article in articles[:5]:
                    title = article.get("title", "")
                    url = article.get("url", "")
                    formatted += f"\n• [{title}]({url})"

        return formatted

    async def _generate_audio(
        self,
        text: str,
        voice: TTSVoice = TTSVoice.ALLOY,
        format: AudioFormat = AudioFormat.OPUS,
    ) -> Dict[str, Any]:
        """Generate TTS audio"""
        
        request = TTSRequest(
            text=text,
            voice=voice,
            format=format,
        )

        response = await self.tts.synthesize(request)

        return {
            "data": response.audio_data,
            "format": response.format.value,
            "size": len(response.audio_data),
            "duration_ms": response.duration_ms,
            "metadata": response.metadata,
        }

    async def compose_stream(
        self,
        user_id: str,
        text_stream,
        channel: str = "voice",
    ):
        """
        Compose streaming response
        
        Args:
            user_id: User identifier
            text_stream: Async generator of text chunks
            channel: Output channel
            
        Yields:
            Response chunks
        """
        accumulated_text = ""
        
        async for chunk in text_stream:
            accumulated_text += chunk
            
            yield {
                "type": "stream_chunk",
                "channel": channel,
                "text": chunk,
                "accumulated": accumulated_text,
            }

        # Final response
        yield {
            "type": "stream_complete",
            "channel": channel,
            "text": accumulated_text,
        }


# Global instance
response_composer = ResponseComposer()
