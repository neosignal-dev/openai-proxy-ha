"""Base TTS provider interface"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from dataclasses import dataclass
from enum import Enum


class AudioFormat(str, Enum):
    """Supported audio formats"""
    MP3 = "mp3"
    OPUS = "opus"
    AAC = "aac"
    FLAC = "flac"
    WAV = "wav"
    PCM = "pcm"


class TTSVoice(str, Enum):
    """Available TTS voices"""
    ALLOY = "alloy"
    ECHO = "echo"
    FABLE = "fable"
    ONYX = "onyx"
    NOVA = "nova"
    SHIMMER = "shimmer"


@dataclass
class TTSRequest:
    """TTS synthesis request"""
    text: str
    voice: TTSVoice = TTSVoice.ALLOY
    format: AudioFormat = AudioFormat.OPUS
    speed: float = 1.0  # 0.25 to 4.0
    language: Optional[str] = None


@dataclass
class TTSResponse:
    """TTS synthesis response"""
    audio_data: bytes
    format: AudioFormat
    duration_ms: Optional[int] = None
    text_length: int = 0
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseTTSProvider(ABC):
    """
    Abstract base class for TTS providers.
    
    Responsibilities:
    - Synthesize text to speech
    - Support multiple voices and formats
    - Handle streaming for long texts
    - Provide consistent interface across providers
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize TTS provider resources"""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup TTS provider resources"""
        pass

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """
        Synthesize text to speech
        
        Args:
            request: TTS request
            
        Returns:
            TTS response with audio data
        """
        pass

    @abstractmethod
    async def stream_synthesize(
        self,
        request: TTSRequest,
        chunk_size: int = 4096,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream speech synthesis for long texts
        
        Args:
            request: TTS request
            chunk_size: Audio chunk size
            
        Yields:
            Audio data chunks
        """
        pass

    @abstractmethod
    async def get_voices(self) -> list[TTSVoice]:
        """
        Get available voices
        
        Returns:
            List of available voices
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """
        Check TTS provider health
        
        Returns:
            Health status dictionary
        """
        pass

    def split_text_for_synthesis(
        self,
        text: str,
        max_length: int = 4096,
    ) -> list[str]:
        """
        Split long text into chunks for synthesis
        
        Args:
            text: Text to split
            max_length: Maximum length per chunk
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        sentences = text.split(". ")
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 <= max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def estimate_duration_ms(
        self,
        text: str,
        words_per_minute: int = 150,
    ) -> int:
        """
        Estimate audio duration from text
        
        Args:
            text: Text content
            words_per_minute: Speaking rate
            
        Returns:
            Estimated duration in milliseconds
        """
        word_count = len(text.split())
        minutes = word_count / words_per_minute
        return int(minutes * 60 * 1000)
