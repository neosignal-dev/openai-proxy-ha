"""Long-term memory using ChromaDB for semantic search"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.services.memory_v2.embeddings import embedding_service
from app.services.memory_v2.policy import MemoryType, MemoryImportance
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LongTermMemory:
    """
    Long-term memory storage using vector database (ChromaDB).
    
    Features:
    - Semantic search across memories
    - Efficient similarity matching
    - Persistent storage
    - Metadata filtering
    - Collections by memory type
    """

    def __init__(self):
        self.client: Optional[chromadb.Client] = None
        self.collections: Dict[str, chromadb.Collection] = {}

    async def initialize(self) -> None:
        """Initialize ChromaDB client and collections"""
        
        self.client = chromadb.Client(
            ChromaSettings(
                persist_directory=settings.chroma_persist_dir,
                anonymized_telemetry=False,
            )
        )

        # Create collections for different memory types
        collection_names = [
            "conversations",
            "preferences",
            "rules",
            "facts",
            "actions",
        ]

        for name in collection_names:
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"description": f"{name.capitalize()} memories"},
            )

        logger.info(
            "Long-term memory initialized",
            collections=len(self.collections),
            persist_dir=settings.chroma_persist_dir,
        )

    async def shutdown(self) -> None:
        """Cleanup resources"""
        self.collections.clear()
        self.client = None
        logger.info("Long-term memory shutdown")

    async def add(
        self,
        user_id: str,
        content: str,
        memory_type: MemoryType = MemoryType.CONVERSATION,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        Add entry to long-term memory
        
        Args:
            user_id: User identifier
            content: Content to remember
            memory_type: Type of memory
            importance: Importance level
            metadata: Optional metadata
            embedding: Optional pre-computed embedding
            
        Returns:
            Memory ID
        """
        if not settings.long_term_memory_enabled:
            return ""

        if not self.client:
            raise RuntimeError("Long-term memory not initialized")

        try:
            # Generate embedding if not provided
            if embedding is None:
                embedding = await embedding_service.embed(content)

            # Generate unique ID
            memory_id = f"{user_id}_{datetime.utcnow().timestamp()}"

            # Determine collection
            collection_name = self._get_collection_name(memory_type)
            collection = self.collections.get(collection_name, self.collections["conversations"])

            # Prepare metadata
            full_metadata = {
                "user_id": user_id,
                "memory_type": memory_type.value,
                "importance": importance.value,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {}),
            }

            # Add to collection
            collection.add(
                embeddings=[embedding],
                documents=[content],
                metadatas=[full_metadata],
                ids=[memory_id],
            )

            logger.debug(
                "Added to long-term memory",
                user_id=user_id,
                memory_id=memory_id,
                memory_type=memory_type.value,
                collection=collection_name,
            )

            return memory_id

        except Exception as e:
            logger.error("Failed to add to long-term memory", error=str(e))
            raise

    async def search(
        self,
        user_id: str,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 5,
        min_similarity: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search long-term memories semantically
        
        Args:
            user_id: User identifier
            query: Search query
            memory_type: Optional type filter
            limit: Maximum results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of matching memories
        """
        if not settings.long_term_memory_enabled:
            return []

        if not self.client:
            raise RuntimeError("Long-term memory not initialized")

        try:
            # Generate query embedding
            query_embedding = await embedding_service.embed(query)

            # Determine which collections to search
            if memory_type:
                collection_name = self._get_collection_name(memory_type)
                collections = [self.collections[collection_name]]
            else:
                # Search all collections
                collections = list(self.collections.values())

            all_results = []

            for collection in collections:
                # Query collection
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    where={"user_id": user_id},
                )

                if results["documents"]:
                    for i in range(len(results["documents"][0])):
                        distance = results["distances"][0][i] if results["distances"] else 0
                        # Convert distance to similarity (1 - distance for L2)
                        similarity = 1 - distance

                        if similarity >= min_similarity:
                            all_results.append({
                                "content": results["documents"][0][i],
                                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                                "similarity": similarity,
                                "distance": distance,
                            })

            # Sort by similarity and limit
            all_results.sort(key=lambda x: x["similarity"], reverse=True)
            final_results = all_results[:limit]

            logger.debug(
                "Long-term memory search",
                user_id=user_id,
                query_length=len(query),
                results=len(final_results),
            )

            return final_results

        except Exception as e:
            logger.error("Long-term memory search failed", error=str(e))
            return []

    async def get_by_type(
        self,
        user_id: str,
        memory_type: MemoryType,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get memories by type
        
        Args:
            user_id: User identifier
            memory_type: Memory type
            limit: Maximum results
            
        Returns:
            List of memories
        """
        if not settings.long_term_memory_enabled:
            return []

        collection_name = self._get_collection_name(memory_type)
        collection = self.collections.get(collection_name)

        if not collection:
            return []

        try:
            results = collection.get(
                where={"user_id": user_id},
                limit=limit,
            )

            memories = []
            if results["documents"]:
                for i in range(len(results["documents"])):
                    memories.append({
                        "id": results["ids"][i],
                        "content": results["documents"][i],
                        "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    })

            return memories

        except Exception as e:
            logger.error("Failed to get memories by type", error=str(e))
            return []

    async def delete(
        self,
        memory_id: str,
    ) -> bool:
        """
        Delete memory by ID
        
        Args:
            memory_id: Memory identifier
            
        Returns:
            True if deleted
        """
        if not self.client:
            return False

        # Try to delete from all collections
        deleted = False
        for collection in self.collections.values():
            try:
                collection.delete(ids=[memory_id])
                deleted = True
                logger.debug("Deleted from long-term memory", memory_id=memory_id)
            except:
                pass

        return deleted

    async def cleanup_expired(
        self,
        user_id: Optional[str] = None,
    ) -> int:
        """
        Cleanup expired memories
        
        Args:
            user_id: Optional user filter
            
        Returns:
            Number of deleted entries
        """
        current_time = datetime.utcnow()
        deleted_count = 0

        for collection in self.collections.values():
            try:
                # Get all entries
                where_filter = {"user_id": user_id} if user_id else {}
                results = collection.get(where=where_filter)

                if results["metadatas"]:
                    for i, metadata in enumerate(results["metadatas"]):
                        expires_at_str = metadata.get("expires_at")
                        if expires_at_str:
                            expires_at = datetime.fromisoformat(expires_at_str)
                            if current_time >= expires_at:
                                memory_id = results["ids"][i]
                                collection.delete(ids=[memory_id])
                                deleted_count += 1

            except Exception as e:
                logger.error("Cleanup failed for collection", error=str(e))

        if deleted_count > 0:
            logger.info("Cleaned up expired memories", count=deleted_count)

        return deleted_count

    def _get_collection_name(self, memory_type: MemoryType) -> str:
        """Get collection name for memory type"""
        mapping = {
            MemoryType.CONVERSATION: "conversations",
            MemoryType.PREFERENCE: "preferences",
            MemoryType.RULE: "rules",
            MemoryType.FACT: "facts",
            MemoryType.ACTION: "actions",
            MemoryType.ERROR: "conversations",  # Errors go to conversations
        }
        return mapping.get(memory_type, "conversations")

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get long-term memory statistics"""
        
        stats = {
            "collections": {},
            "total": 0,
        }

        for name, collection in self.collections.items():
            try:
                results = collection.get(where={"user_id": user_id})
                count = len(results["ids"]) if results["ids"] else 0
                stats["collections"][name] = count
                stats["total"] += count
            except:
                stats["collections"][name] = 0

        return stats


# Global instance
long_term_memory = LongTermMemory()
