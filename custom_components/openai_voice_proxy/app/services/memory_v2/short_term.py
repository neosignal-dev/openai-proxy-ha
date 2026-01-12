"""Short-term memory using SQLite for fast access"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, desc, and_
from app.core.database import DialogHistory, async_session_maker
from app.services.memory_v2.policy import MemoryType, MemoryImportance
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShortTermMemory:
    """
    Short-term memory storage using SQL database.
    
    Features:
    - Fast access to recent conversations
    - Configurable window size
    - Automatic cleanup of old entries
    - Efficient querying by user and time
    """

    def __init__(self, max_size: int = None):
        self.max_size = max_size or settings.short_term_memory_size

    async def add(
        self,
        user_id: str,
        role: str,
        content: str,
        memory_type: MemoryType = MemoryType.CONVERSATION,
        importance: MemoryImportance = MemoryImportance.LOW,
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> int:
        """
        Add entry to short-term memory
        
        Args:
            user_id: User identifier
            role: Message role
            content: Content
            memory_type: Type of memory
            importance: Importance level
            metadata: Optional metadata
            expires_at: Optional expiration date
            
        Returns:
            Entry ID
        """
        async with async_session_maker() as session:
            entry = DialogHistory(
                user_id=user_id,
                role=role,
                content=content,
                memory_type=memory_type.value,
                importance=importance.value,
                expires_at=expires_at,
                extra_data=metadata or {},
            )
            session.add(entry)
            await session.commit()
            entry_id = entry.id

        logger.debug(
            "Added to short-term memory",
            user_id=user_id,
            entry_id=entry_id,
            memory_type=memory_type.value,
        )

        # Cleanup old entries if over limit
        await self._cleanup_old_entries(user_id)

        return entry_id

    async def get_recent(
        self,
        user_id: str,
        limit: Optional[int] = None,
        memory_type: Optional[MemoryType] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent memories
        
        Args:
            user_id: User identifier
            limit: Maximum number of entries
            memory_type: Optional type filter
            
        Returns:
            List of memory entries
        """
        if limit is None:
            limit = self.max_size

        async with async_session_maker() as session:
            query = select(DialogHistory).where(
                DialogHistory.user_id == user_id
            )

            # Filter by type if specified (now uses indexed column!)
            if memory_type:
                query = query.where(DialogHistory.memory_type == memory_type.value)

            query = query.order_by(desc(DialogHistory.timestamp)).limit(limit)

            result = await session.execute(query)
            entries = result.scalars().all()

        memories = []
        for entry in reversed(entries):
            memories.append({
                "id": entry.id,
                "role": entry.role,
                "content": entry.content,
                "timestamp": entry.timestamp.isoformat(),
                "memory_type": entry.memory_type,
                "importance": entry.importance,
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                "extra_data": entry.extra_data,
            })

        logger.debug(
            "Retrieved short-term memories",
            user_id=user_id,
            count=len(memories),
        )

        return memories

    async def get_by_timerange(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Get memories within time range
        
        Args:
            user_id: User identifier
            start_time: Start time
            end_time: End time
            
        Returns:
            List of memory entries
        """
        async with async_session_maker() as session:
            query = select(DialogHistory).where(
                and_(
                    DialogHistory.user_id == user_id,
                    DialogHistory.timestamp >= start_time,
                    DialogHistory.timestamp <= end_time,
                )
            ).order_by(DialogHistory.timestamp)

            result = await session.execute(query)
            entries = result.scalars().all()

        memories = []
        for entry in entries:
            memories.append({
                "id": entry.id,
                "role": entry.role,
                "content": entry.content,
                "timestamp": entry.timestamp.isoformat(),
                "extra_data": entry.extra_data,
            })

        return memories

    async def get_by_importance(
        self,
        user_id: str,
        min_importance: MemoryImportance,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get memories by minimum importance level
        
        Args:
            user_id: User identifier
            min_importance: Minimum importance level
            limit: Maximum results
            
        Returns:
            List of memory entries
        """
        importance_order = [
            MemoryImportance.LOW,
            MemoryImportance.MEDIUM,
            MemoryImportance.HIGH,
            MemoryImportance.CRITICAL,
        ]
        
        min_level = importance_order.index(min_importance)
        allowed_levels = [lvl.value for lvl in importance_order[min_level:]]

        async with async_session_maker() as session:
            query = select(DialogHistory).where(
                and_(
                    DialogHistory.user_id == user_id,
                    DialogHistory.importance.in_(allowed_levels)
                )
            ).order_by(desc(DialogHistory.timestamp)).limit(limit)

            result = await session.execute(query)
            entries = result.scalars().all()

        memories = []
        for entry in entries:
            memories.append({
                "id": entry.id,
                "role": entry.role,
                "content": entry.content,
                "timestamp": entry.timestamp.isoformat(),
                "memory_type": entry.memory_type,
                "importance": entry.importance,
                "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                "extra_data": entry.extra_data,
            })

        return memories

    async def delete(
        self,
        user_id: str,
        entry_id: int,
    ) -> bool:
        """
        Delete entry from short-term memory
        
        Args:
            user_id: User identifier
            entry_id: Entry ID
            
        Returns:
            True if deleted
        """
        async with async_session_maker() as session:
            query = select(DialogHistory).where(
                and_(
                    DialogHistory.id == entry_id,
                    DialogHistory.user_id == user_id,
                )
            )
            result = await session.execute(query)
            entry = result.scalar_one_or_none()

            if entry:
                await session.delete(entry)
                await session.commit()
                logger.debug("Deleted from short-term memory", entry_id=entry_id)
                return True

        return False

    async def _cleanup_old_entries(
        self,
        user_id: str,
    ) -> None:
        """Cleanup old entries beyond max_size"""
        
        async with async_session_maker() as session:
            # Get total count
            query = select(DialogHistory).where(
                DialogHistory.user_id == user_id
            )
            result = await session.execute(query)
            total = len(result.scalars().all())

            if total <= self.max_size:
                return

            # Get IDs to delete (keep most recent max_size)
            query = select(DialogHistory.id).where(
                DialogHistory.user_id == user_id
            ).order_by(desc(DialogHistory.timestamp)).offset(self.max_size)

            result = await session.execute(query)
            ids_to_delete = [row[0] for row in result.all()]

            if ids_to_delete:
                # Delete old entries
                from sqlalchemy import delete
                stmt = delete(DialogHistory).where(
                    DialogHistory.id.in_(ids_to_delete)
                )
                await session.execute(stmt)
                await session.commit()

                logger.debug(
                    "Cleaned up old entries",
                    user_id=user_id,
                    deleted=len(ids_to_delete),
                )

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

        async with async_session_maker() as session:
            # Use indexed column for efficient query
            query = select(DialogHistory).where(
                and_(
                    DialogHistory.expires_at.isnot(None),
                    DialogHistory.expires_at <= current_time
                )
            )
            
            if user_id:
                query = query.where(DialogHistory.user_id == user_id)

            result = await session.execute(query)
            entries = result.scalars().all()

            deleted_count = len(entries)
            
            for entry in entries:
                await session.delete(entry)

            if deleted_count > 0:
                await session.commit()
                logger.info("Cleaned up expired entries", count=deleted_count)

        return deleted_count

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get short-term memory statistics"""
        
        async with async_session_maker() as session:
            query = select(DialogHistory).where(DialogHistory.user_id == user_id)
            result = await session.execute(query)
            entries = result.scalars().all()

        # Count by type and importance
        type_counts = {}
        importance_counts = {}
        
        for entry in entries:
            memory_type = entry.memory_type or "unknown"
            importance = entry.importance or "unknown"
            
            type_counts[memory_type] = type_counts.get(memory_type, 0) + 1
            importance_counts[importance] = importance_counts.get(importance, 0) + 1

        return {
            "total": len(entries),
            "by_type": type_counts,
            "by_importance": importance_counts,
            "max_size": self.max_size,
        }


# Global instance
short_term_memory = ShortTermMemory()
