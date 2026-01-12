"""Memory and context management with Chroma vector database"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import json

# Make ChromaDB optional
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None
    Settings = None
    CHROMADB_AVAILABLE = False

from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import DialogHistory, UserRule, async_session_maker
from sqlalchemy import select, desc

logger = get_logger(__name__)


class MemoryService:
    """Service for managing short-term and long-term memory"""

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Initialize Chroma if available
        if CHROMADB_AVAILABLE:
            self.chroma_client = chromadb.Client(
                Settings(
                    persist_directory=settings.chroma_persist_dir,
                    anonymized_telemetry=False,
                )
            )
        else:
            self.chroma_client = None
            logger.warning("ChromaDB not available. Vector search disabled.")
        
        # Create or get collections
        self.conversations_collection = self.chroma_client.get_or_create_collection(
            name="conversations",
            metadata={"description": "User conversations and dialog history"}
        )
        
        self.preferences_collection = self.chroma_client.get_or_create_collection(
            name="preferences",
            metadata={"description": "User preferences and rules"}
        )
        
        logger.info("Memory service initialized", persist_dir=settings.chroma_persist_dir)

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error("Failed to get embedding", error=str(e))
            raise

    async def add_to_short_term(
        self,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add message to short-term memory (SQL database)
        
        Args:
            user_id: User identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
        """
        async with async_session_maker() as session:
            dialog = DialogHistory(
                user_id=user_id,
                role=role,
                content=content,
                extra_data=metadata or {},
            )
            session.add(dialog)
            await session.commit()

        logger.debug("Added to short-term memory", user_id=user_id, role=role)

    async def get_short_term_history(
        self,
        user_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history
        
        Args:
            user_id: User identifier
            limit: Maximum number of messages (default from settings)
            
        Returns:
            List of messages
        """
        if limit is None:
            limit = settings.short_term_memory_size

        async with async_session_maker() as session:
            result = await session.execute(
                select(DialogHistory)
                .where(DialogHistory.user_id == user_id)
                .order_by(desc(DialogHistory.timestamp))
                .limit(limit)
            )
            dialogs = result.scalars().all()

        # Convert to dict and reverse (oldest first)
        messages = []
        for dialog in reversed(dialogs):
            messages.append({
                "role": dialog.role,
                "content": dialog.content,
                "timestamp": dialog.timestamp.isoformat(),
                "extra_data": dialog.extra_data,
            })

        logger.debug("Retrieved short-term history", user_id=user_id, count=len(messages))
        return messages

    async def add_to_long_term(
        self,
        user_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add to long-term memory (vector database)
        
        Args:
            user_id: User identifier
            content: Content to remember
            metadata: Optional metadata
        """
        if not settings.long_term_memory_enabled:
            return

        try:
            # Get embedding
            embedding = await self.get_embedding(content)

            # Store in Chroma
            doc_id = f"{user_id}_{datetime.utcnow().timestamp()}"
            self.conversations_collection.add(
                embeddings=[embedding],
                documents=[content],
                metadatas=[{
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(metadata or {}),
                }],
                ids=[doc_id],
            )

            logger.debug("Added to long-term memory", user_id=user_id, doc_id=doc_id)

        except Exception as e:
            logger.error("Failed to add to long-term memory", error=str(e))

    async def search_long_term(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search long-term memory
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results
            
        Returns:
            List of relevant memories
        """
        if not settings.long_term_memory_enabled:
            return []

        try:
            # Get query embedding
            query_embedding = await self.get_embedding(query)

            # Search in Chroma
            results = self.conversations_collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where={"user_id": user_id},
            )

            memories = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    memories.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })

            logger.debug("Searched long-term memory", user_id=user_id, results=len(memories))
            return memories

        except Exception as e:
            logger.error("Failed to search long-term memory", error=str(e))
            return []

    async def add_user_rule(
        self,
        user_id: str,
        rule_text: str,
        rule_type: str = "preference",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Add user preference or rule
        
        Args:
            user_id: User identifier
            rule_text: Rule description
            rule_type: Rule type (preference, automation, constraint)
            metadata: Optional metadata
            
        Returns:
            Rule ID
        """
        async with async_session_maker() as session:
            rule = UserRule(
                user_id=user_id,
                rule_text=rule_text,
                rule_type=rule_type,
                active=True,
                extra_data=metadata or {},
            )
            session.add(rule)
            await session.commit()
            rule_id = rule.id

        # Also add to vector database for semantic search
        if settings.long_term_memory_enabled:
            try:
                embedding = await self.get_embedding(rule_text)
                self.preferences_collection.add(
                    embeddings=[embedding],
                    documents=[rule_text],
                    metadatas=[{
                        "user_id": user_id,
                        "rule_id": rule_id,
                        "rule_type": rule_type,
                        "timestamp": datetime.utcnow().isoformat(),
                    }],
                    ids=[f"rule_{rule_id}"],
                )
            except Exception as e:
                logger.error("Failed to add rule to vector DB", error=str(e))

        logger.info("User rule added", user_id=user_id, rule_id=rule_id, rule_type=rule_type)
        return rule_id

    async def get_user_rules(
        self,
        user_id: str,
        rule_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user rules
        
        Args:
            user_id: User identifier
            rule_type: Optional filter by rule type
            
        Returns:
            List of rules
        """
        async with async_session_maker() as session:
            query = select(UserRule).where(
                UserRule.user_id == user_id,
                UserRule.active == True,
            )
            
            if rule_type:
                query = query.where(UserRule.rule_type == rule_type)

            result = await session.execute(query)
            rules = result.scalars().all()

        rules_list = []
        for rule in rules:
            rules_list.append({
                "id": rule.id,
                "rule_text": rule.rule_text,
                "rule_type": rule.rule_type,
                "created_at": rule.created_at.isoformat(),
                "extra_data": rule.extra_data,
            })

        logger.debug("Retrieved user rules", user_id=user_id, count=len(rules_list))
        return rules_list

    async def search_relevant_rules(
        self,
        user_id: str,
        query: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search for relevant user rules based on query
        
        Args:
            user_id: User identifier
            query: Query to match against rules
            limit: Maximum results
            
        Returns:
            List of relevant rules
        """
        if not settings.long_term_memory_enabled:
            # Fallback to getting all rules
            return await self.get_user_rules(user_id)

        try:
            query_embedding = await self.get_embedding(query)

            results = self.preferences_collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where={"user_id": user_id},
            )

            rules = []
            if results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    rules.append({
                        "rule_text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    })

            logger.debug("Searched relevant rules", user_id=user_id, results=len(rules))
            return rules

        except Exception as e:
            logger.error("Failed to search rules", error=str(e))
            return []

    async def build_context(
        self,
        user_id: str,
        current_query: str,
        ha_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build complete context for LLM
        
        Args:
            user_id: User identifier
            current_query: Current user query
            ha_context: Optional Home Assistant context
            
        Returns:
            Complete context dictionary
        """
        # Get short-term history
        recent_history = await self.get_short_term_history(user_id)

        # Search long-term memory
        relevant_memories = await self.search_long_term(user_id, current_query, limit=3)

        # Get relevant rules
        relevant_rules = await self.search_relevant_rules(user_id, current_query, limit=3)

        context = {
            "user_id": user_id,
            "recent_history": recent_history,
            "relevant_memories": relevant_memories,
            "relevant_rules": relevant_rules,
            "ha_context": ha_context or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Context built",
            user_id=user_id,
            history_items=len(recent_history),
            memories=len(relevant_memories),
            rules=len(relevant_rules),
        )

        return context


# Global memory service instance
memory_service = MemoryService()


