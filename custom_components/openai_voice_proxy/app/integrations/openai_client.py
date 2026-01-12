"""OpenAI integration - TTS and Realtime API"""

import json
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any, List
from io import BytesIO
import openai
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAITTSClient:
    """OpenAI Text-to-Speech client"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_tts_model
        self.voice = settings.openai_tts_voice

    async def synthesize_speech(
        self,
        text: str,
        format: str = "opus",  # opus, mp3, flac, wav
        speed: float = 1.0
    ) -> bytes:
        """Synthesize speech from text
        
        Args:
            text: Text to synthesize
            format: Audio format (opus, mp3, flac, wav)
            speed: Speech speed (0.25 to 4.0)
            
        Returns:
            Audio data as bytes
        """
        try:
            logger.info(
                "Synthesizing speech",
                text_length=len(text),
                format=format,
                voice=self.voice,
            )

            response = await self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format=format,
                speed=speed,
            )

            # Get audio content
            audio_bytes = response.content

            logger.info(
                "Speech synthesis completed",
                audio_size=len(audio_bytes),
            )

            return audio_bytes

        except Exception as e:
            logger.error("Speech synthesis failed", error=str(e))
            raise

    async def stream_speech(
        self,
        text: str,
        format: str = "opus",
        speed: float = 1.0,
        chunk_size: int = 4096,
    ) -> AsyncGenerator[bytes, None]:
        """Stream speech synthesis
        
        Args:
            text: Text to synthesize
            format: Audio format
            speed: Speech speed
            chunk_size: Chunk size for streaming
            
        Yields:
            Audio data chunks
        """
        try:
            logger.info("Starting speech streaming", text_length=len(text))

            response = await self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                response_format=format,
                speed=speed,
            )

            # Stream the response
            async for chunk in response.iter_bytes(chunk_size):
                yield chunk

            logger.info("Speech streaming completed")

        except Exception as e:
            logger.error("Speech streaming failed", error=str(e))
            raise


class OpenAIRealtimeClient:
    """OpenAI Realtime API client for WebSocket communication"""

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_realtime_model
        self.ws: Optional[Any] = None
        self.connected = False

    async def connect(self) -> None:
        """Connect to OpenAI Realtime API"""
        try:
            # Note: OpenAI Realtime API uses WebSocket
            # This is a placeholder - actual implementation would use websockets library
            logger.info("Connecting to OpenAI Realtime API", model=self.model)
            
            # In production, use:
            # import websockets
            # url = f"wss://api.openai.com/v1/realtime?model={self.model}"
            # self.ws = await websockets.connect(
            #     url,
            #     extra_headers={"Authorization": f"Bearer {self.api_key}"}
            # )
            
            self.connected = True
            logger.info("Connected to OpenAI Realtime API")

        except Exception as e:
            logger.error("Failed to connect to Realtime API", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from Realtime API"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("Disconnected from OpenAI Realtime API")

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data to Realtime API
        
        Args:
            audio_data: Audio bytes to send
        """
        if not self.connected:
            raise RuntimeError("Not connected to Realtime API")

        try:
            message = {
                "type": "input_audio_buffer.append",
                "audio": audio_data.hex(),
            }
            await self.ws.send(json.dumps(message))

        except Exception as e:
            logger.error("Failed to send audio", error=str(e))
            raise

    async def commit_audio(self) -> None:
        """Commit audio buffer for processing"""
        if not self.connected:
            raise RuntimeError("Not connected to Realtime API")

        try:
            message = {"type": "input_audio_buffer.commit"}
            await self.ws.send(json.dumps(message))

        except Exception as e:
            logger.error("Failed to commit audio", error=str(e))
            raise

    async def send_text(self, text: str, role: str = "user") -> None:
        """Send text message
        
        Args:
            text: Text content
            role: Message role (user, assistant, system)
        """
        if not self.connected:
            raise RuntimeError("Not connected to Realtime API")

        try:
            message = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": role,
                    "content": [{"type": "text", "text": text}],
                },
            }
            await self.ws.send(json.dumps(message))

            # Trigger response
            response_message = {"type": "response.create"}
            await self.ws.send(json.dumps(response_message))

        except Exception as e:
            logger.error("Failed to send text", error=str(e))
            raise

    async def configure_session(
        self,
        instructions: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.8,
        max_tokens: int = 1000,
    ) -> None:
        """Configure Realtime session
        
        Args:
            instructions: System instructions for the assistant
            tools: Available tools for function calling
            temperature: Response temperature
            max_tokens: Maximum response tokens
        """
        if not self.connected:
            raise RuntimeError("Not connected to Realtime API")

        try:
            config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": instructions,
                    "voice": settings.openai_tts_voice,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                    },
                    "temperature": temperature,
                    "max_response_output_tokens": max_tokens,
                },
            }

            if tools:
                config["session"]["tools"] = tools

            await self.ws.send(json.dumps(config))
            logger.info("Realtime session configured")

        except Exception as e:
            logger.error("Failed to configure session", error=str(e))
            raise

    async def receive_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Receive events from Realtime API
        
        Yields:
            Event dictionaries
        """
        if not self.connected:
            raise RuntimeError("Not connected to Realtime API")

        try:
            async for message in self.ws:
                event = json.loads(message)
                
                logger.debug("Received event", event_type=event.get("type"))
                yield event

        except Exception as e:
            logger.error("Error receiving events", error=str(e))
            raise

    async def handle_function_call(
        self,
        call_id: str,
        result: Any
    ) -> None:
        """Send function call result back to API
        
        Args:
            call_id: Function call ID
            result: Function result
        """
        if not self.connected:
            raise RuntimeError("Not connected to Realtime API")

        try:
            message = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result),
                },
            }
            await self.ws.send(json.dumps(message))

            # Trigger response
            response_message = {"type": "response.create"}
            await self.ws.send(json.dumps(response_message))

        except Exception as e:
            logger.error("Failed to handle function call", error=str(e))
            raise


# Global instances
tts_client = OpenAITTSClient()
realtime_client = OpenAIRealtimeClient()


