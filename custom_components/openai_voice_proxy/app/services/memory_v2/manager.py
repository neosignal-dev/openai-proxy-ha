"""Memory manager - unified interface with policy-based decisions"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services.memory_v2.short_term import short_term_memory
from app.services.memory_v2.long_term import long_term_memory
from app.services.memory_v2.embeddings import embedding_service
from app.services.memory_v2.policy import memory_policy, MemoryType, MemoryImportance
from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """
    Unified memory management interface with policy-based decisions.
    
    Features:
    - Automatic policy-based storage decisions
    - Transparent short/long-term management
    - Smart search across both stores
    - Automatic cleanup
    - Statistics and monitoring
    """

    def __init__(self):
        self.short_term = short_term_memory
        self.long_term = long_term_memory
        self.embeddings = embedding_service
        self.policy = memory_policy

    async def initialize(self) -> None:
        """Initialize memory manager"""
        await self.embeddings.initialize()
        await self.long_term.initialize()
        logger.info("Memory manager initialized")

    async def shutdown(self) -> None:
        """Shutdown memory manager"""
        await self.embeddings.shutdown()
        await self.long_term.shutdown()
        logger.info("Memory manager shutdown")

    async def remember(
        self,
        user_id: str,
        content: str,
        role: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
        memory_type: Optional[MemoryType] = None,
    ) -> Dict[str, Any]:
        """
        Remember content using policy-based decisions
        
        Args:
            user_id: User identifier
            content: Content to remember
            role: Message role (user, assistant, system)
            metadata: Optional metadata
            memory_type: Optional explicit memory type
            
        Returns:
            Dictionary with storage info
        """
        # Classify if not provided
        if memory_type is None:
            memory_type = self.policy.classify_content(content, role, metadata)

        # Check if should save
        if not self.policy.should_save(content, memory_type, metadata):
            logger.debug("Not saving - filtered by policy", content_length=len(content))
            return {
                "saved": False,
                "reason": "filtered_by_policy",
            }

        # Determine importance
        importance = self.policy.determine_importance(content, memory_type, metadata)

        # Get expiration date
        expires_at = self.policy.get_expiration_date(importance)

        # Save to short-term
        saved_to = []
        short_term_id = None
        
        if self.policy.should_save_to_short_term(importance):
            short_term_id = await self.short_term.add(
                user_id=user_id,
                role=role,
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata=metadata,
                expires_at=expires_at,
            )
            saved_to.append("short_term")

        # Save to long-term
        long_term_id = None
        
        if self.policy.should_save_to_long_term(importance):
            long_term_id = await self.long_term.add(
                user_id=user_id,
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata={
                    **(metadata or {}),
                    "role": role,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )
            saved_to.append("long_term")

        logger.info(
            "Memory saved",
            user_id=user_id,
            memory_type=memory_type.value,
            importance=importance.value,
            saved_to=saved_to,
        )

        return {
            "saved": True,
            "memory_type": memory_type.value,
            "importance": importance.value,
            "saved_to": saved_to,
            "short_term_id": short_term_id,
            "long_term_id": long_term_id,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }

    async def recall(
        self,
        user_id: str,
        query: str,
        memory_type: Optional[MemoryType] = None,
        search_strategy: str = "hybrid",  # hybrid, semantic, recent
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Recall memories based on query
        
        Args:
            user_id: User identifier
            query: Search query
            memory_type: Optional type filter
            search_strategy: Search strategy (hybrid, semantic, recent)
            limit: Maximum results
            
        Returns:
            List of relevant memories
        """
        logger.info(
            "Recalling memories",
            user_id=user_id,
            query_length=len(query),
            strategy=search_strategy,
        )

        if search_strategy == "recent":
            # Only recent from short-term
            return await self.short_term.get_recent(user_id, limit, memory_type)

        elif search_strategy == "semantic":
            # Only semantic from long-term
            return await self.long_term.search(user_id, query, memory_type, limit)

        else:  # hybrid
            # Combine recent and semantic
            recent = await self.short_term.get_recent(user_id, limit // 2, memory_type)
            semantic = await self.long_term.search(user_id, query, memory_type, limit // 2)

            # Merge and deduplicate
            merged = recent + semantic
            
            # Remove duplicates by content
            seen = set()
            unique = []
            for mem in merged:
                content = mem.get("content", "")
                if content not in seen:
                    seen.add(content)
                    unique.append(mem)

            # Sort by timestamp (recent first) and limit
            unique.sort(
                key=lambda x: x.get("timestamp", x.get("metadata", {}).get("timestamp", "")),
                reverse=True,
            )

            return unique[:limit]

    async def remember_conversation(
        self,
        user_id: str,
        user_message: str,
        assistant_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Remember a complete conversation turn
        
        Args:
            user_id: User identifier
            user_message: User message
            assistant_message: Assistant message
            metadata: Optional metadata
            
        Returns:
            Storage info
        """
        # Save user message
        user_result = await self.remember(
            user_id=user_id,
            content=user_message,
            role="user",
            metadata=metadata,
        )

        # Save assistant message
        assistant_result = await self.remember(
            user_id=user_id,
            content=assistant_message,
            role="assistant",
            metadata=metadata,
        )

        return {
            "user": user_result,
            "assistant": assistant_result,
        }

    async def remember_rule(
        self,
        user_id: str,
        rule_text: str,
        rule_type: str = "preference",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Remember user rule/preference
        
        Args:
            user_id: User identifier
            rule_text: Rule text
            rule_type: Rule type
            metadata: Optional metadata
            
        Returns:
            Storage info
        """
        return await self.remember(
            user_id=user_id,
            content=rule_text,
            role="user",
            memory_type=MemoryType.RULE,
            metadata={
                **(metadata or {}),
                "rule_type": rule_type,
            },
        )

    async def get_rules(
        self,
        user_id: str,
        rule_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get user rules
        
        Args:
            user_id: User identifier
            rule_type: Optional rule type filter
            
        Returns:
            List of rules
        """
        rules = await self.long_term.get_by_type(user_id, MemoryType.RULE, limit=50)

        if rule_type:
            rules = [r for r in rules if r.get("metadata", {}).get("rule_type") == rule_type]

        return rules

    async def search_rules(
        self,
        user_id: str,
        query: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search relevant rules for query
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results
            
        Returns:
            List of relevant rules
        """
        return await self.long_term.search(
            user_id=user_id,
            query=query,
            memory_type=MemoryType.RULE,
            limit=limit,
        )

    async def build_context(
        self,
        user_id: str,
        current_query: str,
        include_recent: bool = True,
        include_relevant: bool = True,
        include_rules: bool = True,
    ) -> Dict[str, Any]:
        """
        Build complete memory context for LLM
        
        Args:
            user_id: User identifier
            current_query: Current query
            include_recent: Include recent history
            include_relevant: Include relevant long-term memories
            include_rules: Include user rules
            
        Returns:
            Complete context dictionary
        """
        context = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "recent_history": [],
            "relevant_memories": [],
            "user_rules": [],
        }

        # Recent history
        if include_recent:
            context["recent_history"] = await self.short_term.get_recent(user_id, limit=10)

        # Relevant memories
        if include_relevant:
            context["relevant_memories"] = await self.long_term.search(
                user_id=user_id,
                query=current_query,
                limit=3,
            )

        # User rules
        if include_rules:
            context["user_rules"] = await self.search_rules(user_id, current_query, limit=3)

        logger.info(
            "Context built",
            user_id=user_id,
            recent=len(context["recent_history"]),
            relevant=len(context["relevant_memories"]),
            rules=len(context["user_rules"]),
        )

        return context

    async def cleanup(
        self,
        user_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Cleanup expired memories
        
        Args:
            user_id: Optional user filter
            
        Returns:
            Cleanup statistics
        """
        logger.info("Running memory cleanup", user_id=user_id)

        short_term_deleted = await self.short_term.cleanup_expired(user_id)
        long_term_deleted = await self.long_term.cleanup_expired(user_id)

        return {
            "short_term_deleted": short_term_deleted,
            "long_term_deleted": long_term_deleted,
            "total_deleted": short_term_deleted + long_term_deleted,
        }

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get memory statistics"""
        
        short_term_stats = await self.short_term.get_stats(user_id)
        long_term_stats = await self.long_term.get_stats(user_id)

        return {
            "user_id": user_id,
            "short_term": short_term_stats,
            "long_term": long_term_stats,
            "total_memories": (
                short_term_stats.get("total", 0) +
                long_term_stats.get("total", 0)
            ),
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check memory system health"""
        
        embeddings_healthy = self.embeddings.client is not None
        long_term_healthy = self.long_term.client is not None

        return {
            "embeddings": "healthy" if embeddings_healthy else "unhealthy",
            "long_term": "healthy" if long_term_healthy else "unhealthy",
            "short_term": "healthy",  # SQL-based, always available
            "overall": "healthy" if (embeddings_healthy and long_term_healthy) else "degraded",
        }


# Global instance
memory_manager = MemoryManager()
