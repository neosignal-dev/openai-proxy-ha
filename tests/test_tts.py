"""Tests for TTS layer"""

import pytest
from app.services.tts.base import (
    BaseTTSProvider,
    TTSRequest,
    TTSVoice,
    AudioFormat,
)


class TestTTSBase:
    """Test TTS base classes and utilities"""

    def test_tts_request_creation(self):
        """Test TTSRequest creation"""
        request = TTSRequest(
            text="Hello, world!",
            voice=TTSVoice.ALLOY,
            format=AudioFormat.OPUS,
            speed=1.0,
        )
        
        assert request.text == "Hello, world!"
        assert request.voice == TTSVoice.ALLOY
        assert request.format == AudioFormat.OPUS
        assert request.speed == 1.0

    def test_tts_request_defaults(self):
        """Test TTSRequest defaults"""
        request = TTSRequest(text="Test")
        
        assert request.voice == TTSVoice.ALLOY
        assert request.format == AudioFormat.OPUS
        assert request.speed == 1.0

    def test_split_text_short(self):
        """Test text splitting for short text"""
        # Create a mock provider instance to access the method
        class MockProvider(BaseTTSProvider):
            async def initialize(self): pass
            async def shutdown(self): pass
            async def synthesize(self, request): pass
            async def stream_synthesize(self, request, chunk_size): pass
            async def get_voices(self): pass
            async def health_check(self): pass
        
        provider = MockProvider()
        text = "This is a short text."
        chunks = provider.split_text_for_synthesis(text, max_length=100)
        
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_text_long(self):
        """Test text splitting for long text"""
        class MockProvider(BaseTTSProvider):
            async def initialize(self): pass
            async def shutdown(self): pass
            async def synthesize(self, request): pass
            async def stream_synthesize(self, request, chunk_size): pass
            async def get_voices(self): pass
            async def health_check(self): pass
        
        provider = MockProvider()
        text = ". ".join([f"Sentence {i}" for i in range(20)])
        chunks = provider.split_text_for_synthesis(text, max_length=50)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 50 for chunk in chunks)

    def test_estimate_duration(self):
        """Test audio duration estimation"""
        class MockProvider(BaseTTSProvider):
            async def initialize(self): pass
            async def shutdown(self): pass
            async def synthesize(self, request): pass
            async def stream_synthesize(self, request, chunk_size): pass
            async def get_voices(self): pass
            async def health_check(self): pass
        
        provider = MockProvider()
        
        # 150 words/minute = 2.5 words/second
        # 10 words = 4 seconds = 4000ms
        text = " ".join(["word"] * 10)
        duration = provider.estimate_duration_ms(text, words_per_minute=150)
        
        assert duration == 4000
