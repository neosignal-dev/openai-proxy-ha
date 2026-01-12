"""Embedding service for semantic memory search"""

from typing import List, Optional
import numpy as np
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Service for generating and managing embeddings.
    
    Features:
    - Generate embeddings using OpenAI
    - Cache embeddings
    - Batch processing
    - Similarity computation
    """

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self.client: Optional[AsyncOpenAI] = None
        self.cache: dict[str, List[float]] = {}

    async def initialize(self) -> None:
        """Initialize embedding service"""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        logger.info("Embedding service initialized", model=self.model)

    async def shutdown(self) -> None:
        """Cleanup resources"""
        if self.client:
            await self.client.close()
            self.client = None
        self.cache.clear()
        logger.info("Embedding service shutdown")

    async def embed(
        self,
        text: str,
        use_cache: bool = True,
    ) -> List[float]:
        """
        Generate embedding for text
        
        Args:
            text: Text to embed
            use_cache: Use cached embedding if available
            
        Returns:
            Embedding vector
        """
        if not self.client:
            raise RuntimeError("Embedding service not initialized")

        # Check cache
        if use_cache and text in self.cache:
            logger.debug("Using cached embedding")
            return self.cache[text]

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            
            embedding = response.data[0].embedding

            # Cache it
            if use_cache:
                self.cache[text] = embedding

            logger.debug("Embedding generated", text_length=len(text))
            return embedding

        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise

    async def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts
            use_cache: Use cached embeddings
            
        Returns:
            List of embedding vectors
        """
        if not self.client:
            raise RuntimeError("Embedding service not initialized")

        embeddings = []
        texts_to_embed = []
        cached_indices = []

        # Check cache
        for i, text in enumerate(texts):
            if use_cache and text in self.cache:
                embeddings.append(self.cache[text])
                cached_indices.append(i)
            else:
                texts_to_embed.append(text)

        # Generate embeddings for uncached texts
        if texts_to_embed:
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts_to_embed,
                )
                
                for i, data in enumerate(response.data):
                    embedding = data.embedding
                    embeddings.append(embedding)
                    
                    # Cache it
                    if use_cache:
                        self.cache[texts_to_embed[i]] = embedding

                logger.debug(
                    "Batch embeddings generated",
                    total=len(texts),
                    cached=len(cached_indices),
                    generated=len(texts_to_embed),
                )

            except Exception as e:
                logger.error("Batch embedding failed", error=str(e))
                raise

        return embeddings

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score (0-1)
        """
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        
        dot_product = np.dot(arr1, arr2)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))

    @staticmethod
    def euclidean_distance(vec1: List[float], vec2: List[float]) -> float:
        """
        Compute Euclidean distance between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Distance
        """
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        return float(np.linalg.norm(arr1 - arr2))

    def clear_cache(self) -> None:
        """Clear embedding cache"""
        self.cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_size(self) -> int:
        """Get number of cached embeddings"""
        return len(self.cache)


# Global instance
embedding_service = EmbeddingService()
