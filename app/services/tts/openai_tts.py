"""OpenAI TTS provider implementation"""

import time
from typing import AsyncGenerator
from openai import AsyncOpenAI, OpenAIError
from app.services.tts.base import (
    BaseTTSProvider,
    TTSRequest,
    TTSResponse,
    TTSVoice,
    AudioFormat,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAITTSProvider(BaseTTSProvider):
    """
    OpenAI Text-to-Speech provider.
    
    Features:
    - High-quality voices (6 options)
    - Multiple audio formats
    - Low latency
    - Streaming support
    """

    def __init__(
        self,
        model: str = "tts-1-hd",
        default_voice: TTSVoice = TTSVoice.ALLOY,
    ):
        self.model = model
        self.default_voice = default_voice
        self.client: AsyncOpenAI = None

    async def initialize(self) -> None:
        """Initialize OpenAI client"""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        logger.info(
            "OpenAI TTS provider initialized",
            model=self.model,
            voice=self.default_voice.value,
        )

    async def shutdown(self) -> None:
        """Cleanup resources"""
        if self.client:
            await self.client.close()
            self.client = None
        logger.info("OpenAI TTS provider shutdown")

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """
        Synthesize text to speech
        
        Args:
            request: TTS request
            
        Returns:
            TTS response with audio data
        """
        if not self.client:
            raise RuntimeError("TTS provider not initialized")

        start_time = time.time()

        try:
            logger.info(
                "Synthesizing speech",
                text_length=len(request.text),
                voice=request.voice.value,
                format=request.format.value,
            )

            response = await self.client.audio.speech.create(
                model=self.model,
                voice=request.voice.value,
                input=request.text,
                response_format=request.format.value,
                speed=request.speed,
            )

            # Get audio content
            audio_bytes = response.content

            duration_ms = int((time.time() - start_time) * 1000)
            estimated_audio_duration = self.estimate_duration_ms(request.text)

            logger.info(
                "Speech synthesis completed",
                audio_size=len(audio_bytes),
                duration_ms=duration_ms,
            )

            return TTSResponse(
                audio_data=audio_bytes,
                format=request.format,
                duration_ms=estimated_audio_duration,
                text_length=len(request.text),
                metadata={
                    "model": self.model,
                    "voice": request.voice.value,
                    "speed": request.speed,
                    "synthesis_time_ms": duration_ms,
                },
            )

        except OpenAIError as e:
            logger.error("OpenAI TTS error", error=str(e))
            raise

        except Exception as e:
            logger.error("Speech synthesis failed", error=str(e))
            raise

    async def stream_synthesize(
        self,
        request: TTSRequest,
        chunk_size: int = 4096,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream speech synthesis
        
        Args:
            request: TTS request
            chunk_size: Chunk size for streaming
            
        Yields:
            Audio data chunks
        """
        if not self.client:
            raise RuntimeError("TTS provider not initialized")

        try:
            logger.info(
                "Starting speech streaming",
                text_length=len(request.text),
                voice=request.voice.value,
            )

            response = await self.client.audio.speech.create(
                model=self.model,
                voice=request.voice.value,
                input=request.text,
                response_format=request.format.value,
                speed=request.speed,
            )

            # Stream the response
            total_bytes = 0
            async for chunk in response.iter_bytes(chunk_size):
                total_bytes += len(chunk)
                yield chunk

            logger.info(
                "Speech streaming completed",
                total_bytes=total_bytes,
            )

        except OpenAIError as e:
            logger.error("OpenAI TTS streaming error", error=str(e))
            raise

        except Exception as e:
            logger.error("Speech streaming failed", error=str(e))
            raise

    async def synthesize_with_ssml(
        self,
        ssml: str,
        request: TTSRequest,
    ) -> TTSResponse:
        """
        Synthesize SSML (Speech Synthesis Markup Language)
        
        Note: OpenAI TTS doesn't natively support SSML,
        so this method strips tags and uses plain text.
        
        Args:
            ssml: SSML markup
            request: TTS request
            
        Returns:
            TTS response
        """
        import re
        
        # Strip SSML tags (basic implementation)
        text = re.sub(r'<[^>]+>', '', ssml)
        request.text = text
        
        return await self.synthesize(request)

    async def synthesize_long_text(
        self,
        text: str,
        request: TTSRequest,
        max_chunk_length: int = 4000,
    ) -> list[TTSResponse]:
        """
        Synthesize long text by splitting into chunks
        
        Args:
            text: Long text to synthesize
            request: TTS request
            max_chunk_length: Maximum length per chunk
            
        Returns:
            List of TTS responses
        """
        chunks = self.split_text_for_synthesis(text, max_chunk_length)
        
        logger.info(
            "Synthesizing long text",
            total_length=len(text),
            chunks=len(chunks),
        )

        responses = []
        for i, chunk in enumerate(chunks):
            chunk_request = TTSRequest(
                text=chunk,
                voice=request.voice,
                format=request.format,
                speed=request.speed,
                language=request.language,
            )
            
            response = await self.synthesize(chunk_request)
            response.metadata["chunk_index"] = i
            response.metadata["total_chunks"] = len(chunks)
            responses.append(response)

        return responses

    async def get_voices(self) -> list[TTSVoice]:
        """Get available OpenAI TTS voices"""
        return [
            TTSVoice.ALLOY,
            TTSVoice.ECHO,
            TTSVoice.FABLE,
            TTSVoice.ONYX,
            TTSVoice.NOVA,
            TTSVoice.SHIMMER,
        ]

    async def health_check(self) -> dict:
        """Check TTS provider health"""
        healthy = self.client is not None

        if healthy:
            try:
                # Simple test synthesis
                test_request = TTSRequest(
                    text="Test",
                    voice=self.default_voice,
                    format=AudioFormat.OPUS,
                )
                response = await self.synthesize(test_request)
                healthy = len(response.audio_data) > 0
            except Exception as e:
                healthy = False
                logger.error("TTS health check failed", error=str(e))

        return {
            "provider": "openai",
            "model": self.model,
            "healthy": healthy,
            "default_voice": self.default_voice.value,
            "available_voices": len(await self.get_voices()),
        }


# Global instance
openai_tts = OpenAITTSProvider(
    model=settings.openai_tts_model,
    default_voice=TTSVoice(settings.openai_tts_voice),
)
