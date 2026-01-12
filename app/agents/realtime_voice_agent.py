"""Realtime voice agent using OpenAI Realtime API with WebSocket"""

import json
import asyncio
import base64
from typing import Dict, List, Optional, Any, AsyncGenerator
from enum import Enum
import websockets
from websockets.client import WebSocketClientProtocol
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


class RealtimeEventType(str, Enum):
    """OpenAI Realtime API event types"""
    # Session
    SESSION_UPDATE = "session.update"
    SESSION_UPDATED = "session.updated"
    
    # Conversation
    CONVERSATION_ITEM_CREATE = "conversation.item.create"
    CONVERSATION_ITEM_CREATED = "conversation.item.created"
    CONVERSATION_ITEM_TRUNCATE = "conversation.item.truncate"
    
    # Input audio
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    INPUT_AUDIO_BUFFER_COMMIT = "input_audio_buffer.commit"
    INPUT_AUDIO_BUFFER_CLEAR = "input_audio_buffer.clear"
    INPUT_AUDIO_BUFFER_COMMITTED = "input_audio_buffer.committed"
    INPUT_AUDIO_BUFFER_SPEECH_STARTED = "input_audio_buffer.speech_started"
    INPUT_AUDIO_BUFFER_SPEECH_STOPPED = "input_audio_buffer.speech_stopped"
    
    # Response
    RESPONSE_CREATE = "response.create"
    RESPONSE_CREATED = "response.created"
    RESPONSE_DONE = "response.done"
    RESPONSE_CANCEL = "response.cancel"
    RESPONSE_CANCELLED = "response.cancelled"
    
    # Response output
    RESPONSE_OUTPUT_ITEM_ADDED = "response.output_item.added"
    RESPONSE_OUTPUT_ITEM_DONE = "response.output_item.done"
    RESPONSE_CONTENT_PART_ADDED = "response.content_part.added"
    RESPONSE_CONTENT_PART_DONE = "response.content_part.done"
    
    # Audio output
    RESPONSE_AUDIO_DELTA = "response.audio.delta"
    RESPONSE_AUDIO_DONE = "response.audio.done"
    RESPONSE_AUDIO_TRANSCRIPT_DELTA = "response.audio_transcript.delta"
    RESPONSE_AUDIO_TRANSCRIPT_DONE = "response.audio_transcript.done"
    
    # Text output
    RESPONSE_TEXT_DELTA = "response.text.delta"
    RESPONSE_TEXT_DONE = "response.text.done"
    
    # Function calling
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA = "response.function_call_arguments.delta"
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE = "response.function_call_arguments.done"
    
    # Errors
    ERROR = "error"
    RATE_LIMITS_UPDATED = "rate_limits.updated"


class TurnDetectionType(str, Enum):
    """Turn detection types"""
    SERVER_VAD = "server_vad"  # Server-side Voice Activity Detection
    NONE = "none"  # Manual turn detection


class RealtimeVoiceAgent(BaseAgent):
    """
    Voice-first agent using OpenAI Realtime API.
    
    Features:
    - Real-time bidirectional audio streaming
    - Server-side VAD with configurable turn detection
    - Barge-in support (interrupt assistant speech)
    - Function/tool calling during conversation
    - Automatic transcription
    - Low-latency responses
    """

    def __init__(
        self,
        model: str = "gpt-4o-realtime-preview-2024-10-01",
        voice: str = "alloy",
        temperature: float = 0.8,
        max_tokens: int = 1000,
        turn_detection: TurnDetectionType = TurnDetectionType.SERVER_VAD,
    ):
        super().__init__(AgentType.REALTIME)
        self.model = model
        self.voice = voice
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.turn_detection = turn_detection
        
        # WebSocket connection per session
        self.websockets: Dict[str, WebSocketClientProtocol] = {}
        
        # Event handlers for async processing
        self.event_handlers: Dict[str, asyncio.Queue] = {}

    async def initialize(self) -> None:
        """Initialize agent"""
        logger.info(
            "Realtime voice agent initialized",
            model=self.model,
            voice=self.voice,
            turn_detection=self.turn_detection.value,
        )

    async def shutdown(self) -> None:
        """Cleanup all active WebSocket connections"""
        for session_id, ws in list(self.websockets.items()):
            try:
                await ws.close()
            except Exception as e:
                logger.error(
                    "Error closing WebSocket",
                    session_id=session_id,
                    error=str(e),
                )
        
        self.websockets.clear()
        self.event_handlers.clear()
        logger.info("Realtime voice agent shutdown")

    async def connect_session(
        self,
        session_id: str,
        instructions: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Establish WebSocket connection for a session
        
        Args:
            session_id: Session identifier
            instructions: System instructions for the assistant
            tools: Optional tools for function calling
        """
        if session_id in self.websockets:
            logger.warning("Session already connected", session_id=session_id)
            return

        try:
            # Connect to OpenAI Realtime API
            url = f"wss://api.openai.com/v1/realtime?model={self.model}"
            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Beta": "realtime=v1",
            }

            ws = await websockets.connect(url, extra_headers=headers)
            self.websockets[session_id] = ws
            
            # Create event queue for this session
            self.event_handlers[session_id] = asyncio.Queue()

            logger.info("WebSocket connected", session_id=session_id)

            # Configure session
            await self._configure_session(
                session_id=session_id,
                instructions=instructions,
                tools=tools,
            )

            # Start event listener
            asyncio.create_task(self._listen_events(session_id))

        except Exception as e:
            logger.error(
                "Failed to connect session",
                session_id=session_id,
                error=str(e),
            )
            raise

    async def disconnect_session(self, session_id: str) -> None:
        """
        Disconnect WebSocket for a session
        
        Args:
            session_id: Session identifier
        """
        ws = self.websockets.get(session_id)
        if ws:
            try:
                await ws.close()
            except Exception as e:
                logger.error("Error disconnecting", session_id=session_id, error=str(e))
            finally:
                del self.websockets[session_id]
                if session_id in self.event_handlers:
                    del self.event_handlers[session_id]
                
                logger.info("Session disconnected", session_id=session_id)

    async def _configure_session(
        self,
        session_id: str,
        instructions: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Configure Realtime API session"""
        ws = self.websockets.get(session_id)
        if not ws:
            raise RuntimeError(f"No WebSocket for session {session_id}")

        config = {
            "type": RealtimeEventType.SESSION_UPDATE,
            "session": {
                "modalities": ["text", "audio"],
                "instructions": instructions,
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1",
                },
                "turn_detection": self._get_turn_detection_config(),
                "temperature": self.temperature,
                "max_response_output_tokens": self.max_tokens,
            },
        }

        if tools:
            config["session"]["tools"] = tools
            config["session"]["tool_choice"] = "auto"

        await ws.send(json.dumps(config))
        logger.info("Session configured", session_id=session_id)

    def _get_turn_detection_config(self) -> Dict[str, Any]:
        """Get turn detection configuration"""
        if self.turn_detection == TurnDetectionType.SERVER_VAD:
            return {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
            }
        else:
            return {"type": None}

    async def _listen_events(self, session_id: str) -> None:
        """
        Listen for events from WebSocket
        
        Args:
            session_id: Session identifier
        """
        ws = self.websockets.get(session_id)
        if not ws:
            return

        try:
            async for message in ws:
                event = json.loads(message)
                event_type = event.get("type")
                
                logger.debug(
                    "Received event",
                    session_id=session_id,
                    event_type=event_type,
                )

                # Put event in queue for processing
                queue = self.event_handlers.get(session_id)
                if queue:
                    await queue.put(event)

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed", session_id=session_id)
        except Exception as e:
            logger.error(
                "Error in event listener",
                session_id=session_id,
                error=str(e),
            )

    async def send_audio(
        self,
        session_id: str,
        audio_data: bytes,
        commit: bool = False,
    ) -> None:
        """
        Send audio input to Realtime API
        
        Args:
            session_id: Session identifier
            audio_data: PCM16 audio data
            commit: Whether to commit the audio buffer
        """
        ws = self.websockets.get(session_id)
        if not ws:
            raise RuntimeError(f"No WebSocket for session {session_id}")

        # Encode audio to base64
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        # Send append event
        event = {
            "type": RealtimeEventType.INPUT_AUDIO_BUFFER_APPEND,
            "audio": audio_base64,
        }
        await ws.send(json.dumps(event))

        # Commit if requested
        if commit:
            await self.commit_audio(session_id)

    async def commit_audio(self, session_id: str) -> None:
        """
        Commit audio buffer to trigger response
        
        Args:
            session_id: Session identifier
        """
        ws = self.websockets.get(session_id)
        if not ws:
            raise RuntimeError(f"No WebSocket for session {session_id}")

        event = {"type": RealtimeEventType.INPUT_AUDIO_BUFFER_COMMIT}
        await ws.send(json.dumps(event))
        logger.debug("Audio buffer committed", session_id=session_id)

    async def send_text(
        self,
        session_id: str,
        text: str,
        trigger_response: bool = True,
    ) -> None:
        """
        Send text input to Realtime API
        
        Args:
            session_id: Session identifier
            text: Text content
            trigger_response: Whether to trigger assistant response
        """
        ws = self.websockets.get(session_id)
        if not ws:
            raise RuntimeError(f"No WebSocket for session {session_id}")

        # Create conversation item
        event = {
            "type": RealtimeEventType.CONVERSATION_ITEM_CREATE,
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }
        await ws.send(json.dumps(event))

        if trigger_response:
            await self.trigger_response(session_id)

    async def trigger_response(
        self,
        session_id: str,
        modalities: Optional[List[str]] = None,
    ) -> None:
        """
        Manually trigger assistant response
        
        Args:
            session_id: Session identifier
            modalities: Optional modalities (text, audio)
        """
        ws = self.websockets.get(session_id)
        if not ws:
            raise RuntimeError(f"No WebSocket for session {session_id}")

        event = {
            "type": RealtimeEventType.RESPONSE_CREATE,
            "response": {
                "modalities": modalities or ["text", "audio"],
            },
        }
        await ws.send(json.dumps(event))
        logger.debug("Response triggered", session_id=session_id)

    async def cancel_response(self, session_id: str) -> None:
        """
        Cancel ongoing response (barge-in)
        
        Args:
            session_id: Session identifier
        """
        ws = self.websockets.get(session_id)
        if not ws:
            raise RuntimeError(f"No WebSocket for session {session_id}")

        event = {"type": RealtimeEventType.RESPONSE_CANCEL}
        await ws.send(json.dumps(event))
        logger.info("Response cancelled (barge-in)", session_id=session_id)

    async def send_function_result(
        self,
        session_id: str,
        call_id: str,
        output: Any,
    ) -> None:
        """
        Send function call result back to API
        
        Args:
            session_id: Session identifier
            call_id: Function call ID
            output: Function result
        """
        ws = self.websockets.get(session_id)
        if not ws:
            raise RuntimeError(f"No WebSocket for session {session_id}")

        event = {
            "type": RealtimeEventType.CONVERSATION_ITEM_CREATE,
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(output),
            },
        }
        await ws.send(json.dumps(event))

        # Trigger response to continue
        await self.trigger_response(session_id)

    async def process(
        self,
        context: AgentContext,
        input_text: Optional[str] = None,
        input_audio: Optional[bytes] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentResponse:
        """
        Process input (not typically used for realtime - use stream_process instead)
        """
        raise NotImplementedError(
            "Realtime agent is designed for streaming. Use stream_process() instead."
        )

    async def stream_process(
        self,
        context: AgentContext,
        input_text: Optional[str] = None,
        input_audio: Optional[bytes] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[AgentResponse, None]:
        """
        Stream real-time processing with events
        
        Args:
            context: Agent context
            input_text: Optional text input
            input_audio: Optional audio input
            tools: Optional tools
            
        Yields:
            Streaming responses (audio deltas, transcripts, function calls)
        """
        session_id = context.session_id
        if not session_id:
            raise ValueError("Session ID required for realtime agent")

        # Ensure session is connected
        if session_id not in self.websockets:
            instructions = self._build_instructions(context)
            await self.connect_session(session_id, instructions, tools)

        # Send input
        if input_audio:
            await self.send_audio(session_id, input_audio, commit=True)
        elif input_text:
            await self.send_text(session_id, input_text)
        else:
            raise ValueError("Either input_text or input_audio required")

        # Stream events
        queue = self.event_handlers.get(session_id)
        if not queue:
            raise RuntimeError("No event handler for session")

        accumulated_audio = bytearray()
        accumulated_text = ""

        try:
            while True:
                # Get event with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    logger.warning("Event timeout", session_id=session_id)
                    break

                event_type = event.get("type")

                # Audio delta
                if event_type == RealtimeEventType.RESPONSE_AUDIO_DELTA:
                    audio_base64 = event.get("delta", "")
                    if audio_base64:
                        audio_chunk = base64.b64decode(audio_base64)
                        accumulated_audio.extend(audio_chunk)
                        
                        yield AgentResponse(
                            type=ResponseType.AUDIO,
                            content="",
                            audio_data=audio_chunk,
                            audio_format="pcm16",
                            metadata={"event": event_type},
                        )

                # Text delta
                elif event_type == RealtimeEventType.RESPONSE_TEXT_DELTA:
                    text_delta = event.get("delta", "")
                    accumulated_text += text_delta
                    
                    yield AgentResponse(
                        type=ResponseType.TEXT,
                        content=text_delta,
                        metadata={
                            "event": event_type,
                            "accumulated": accumulated_text,
                        },
                    )

                # Transcript delta
                elif event_type == RealtimeEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
                    transcript_delta = event.get("delta", "")
                    
                    yield AgentResponse(
                        type=ResponseType.TEXT,
                        content=transcript_delta,
                        metadata={"event": event_type, "is_transcript": True},
                    )

                # Function call
                elif event_type == RealtimeEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
                    call_id = event.get("call_id")
                    function_name = event.get("name")
                    arguments = event.get("arguments")
                    
                    yield AgentResponse(
                        type=ResponseType.FUNCTION_CALL,
                        content=function_name,
                        metadata={
                            "event": event_type,
                            "call_id": call_id,
                            "function": function_name,
                            "arguments": json.loads(arguments) if arguments else {},
                        },
                    )

                # Response done
                elif event_type == RealtimeEventType.RESPONSE_DONE:
                    response_data = event.get("response", {})
                    usage = response_data.get("usage", {})
                    
                    # Final response
                    yield AgentResponse(
                        type=ResponseType.TEXT,
                        content=accumulated_text or "[Audio response]",
                        audio_data=bytes(accumulated_audio) if accumulated_audio else None,
                        audio_format="pcm16" if accumulated_audio else None,
                        tokens_used=usage.get("total_tokens"),
                        metadata={
                            "event": event_type,
                            "response_id": response_data.get("id"),
                            "status": response_data.get("status"),
                        },
                    )
                    break

                # Error
                elif event_type == RealtimeEventType.ERROR:
                    error_data = event.get("error", {})
                    logger.error(
                        "Realtime API error",
                        session_id=session_id,
                        error=error_data,
                    )
                    break

        except Exception as e:
            logger.error(
                "Stream processing error",
                session_id=session_id,
                error=str(e),
            )
            raise

    def _build_instructions(self, context: AgentContext) -> str:
        """Build system instructions for session"""
        parts = [
            f"Ты — {settings.assistant_name}, умный голосовой ассистент для управления домом через Home Assistant.",
            f"Стиль общения: {', '.join(settings.assistant_style_list)}",
            f"Язык: {settings.assistant_language}",
            "",
            "Отвечай КРАТКО и ЕСТЕСТВЕННО, как в живом разговоре.",
            "Это голосовой интерфейс - избегай длинных списков и форматирования.",
        ]

        if context.user_rules:
            parts.append("")
            parts.append("Правила пользователя:")
            for rule in context.user_rules[:3]:
                parts.append(f"- {rule.get('rule_text', '')}")

        return "\n".join(parts)

    async def health_check(self) -> Dict[str, Any]:
        """Check agent health"""
        active_connections = len(self.websockets)
        healthy = True

        # Check if any connections are alive
        for session_id, ws in list(self.websockets.items()):
            if ws.closed:
                healthy = False
                logger.warning("Dead WebSocket detected", session_id=session_id)

        return {
            "agent_type": self.agent_type.value,
            "model": self.model,
            "voice": self.voice,
            "healthy": healthy,
            "active_sessions": len(self.active_sessions),
            "active_connections": active_connections,
            "turn_detection": self.turn_detection.value,
        }
