"""Memory policy - determines what and how to remember"""

from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime, timedelta
from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryType(str, Enum):
    """Types of memories"""
    CONVERSATION = "conversation"  # General conversation
    PREFERENCE = "preference"  # User preference
    RULE = "rule"  # Explicit rule
    FACT = "fact"  # Factual information
    ACTION = "action"  # Action performed
    ERROR = "error"  # Error occurred


class MemoryImportance(str, Enum):
    """Memory importance levels"""
    LOW = "low"  # Ephemeral, short-term only
    MEDIUM = "medium"  # Keep in short-term, maybe long-term
    HIGH = "high"  # Definitely save to long-term
    CRITICAL = "critical"  # Never forget


class MemoryPolicy:
    """
    Policy engine that determines memory management decisions.
    
    Decisions:
    - Should this be saved?
    - Which storage (short-term, long-term, both)?
    - How long to keep?
    - What importance level?
    - Should this trigger any actions?
    """

    # Retention policies (in days)
    RETENTION_POLICY = {
        MemoryImportance.LOW: 1,  # 1 day
        MemoryImportance.MEDIUM: 7,  # 1 week
        MemoryImportance.HIGH: 30,  # 1 month
        MemoryImportance.CRITICAL: None,  # Forever
    }

    def __init__(self):
        pass

    def should_save(
        self,
        content: str,
        memory_type: MemoryType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Determine if content should be saved
        
        Args:
            content: Memory content
            memory_type: Type of memory
            metadata: Optional metadata
            
        Returns:
            True if should be saved
        """
        # Don't save empty content
        if not content or len(content.strip()) < 3:
            return False

        # Don't save system messages
        if metadata and metadata.get("role") == "system":
            return False

        # Don't save very short acknowledgments
        short_responses = ["ok", "да", "нет", "yes", "no", "хорошо", "понял"]
        if content.lower().strip() in short_responses:
            return False

        # Always save rules and preferences
        if memory_type in [MemoryType.RULE, MemoryType.PREFERENCE]:
            return True

        # Always save actions
        if memory_type == MemoryType.ACTION:
            return True

        # Save conversations longer than 20 chars
        if memory_type == MemoryType.CONVERSATION and len(content) >= 20:
            return True

        # Save facts
        if memory_type == MemoryType.FACT:
            return True

        return False

    def determine_importance(
        self,
        content: str,
        memory_type: MemoryType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryImportance:
        """
        Determine memory importance
        
        Args:
            content: Memory content
            memory_type: Type of memory
            metadata: Optional metadata
            
        Returns:
            Importance level
        """
        # Rules and preferences are critical
        if memory_type in [MemoryType.RULE, MemoryType.PREFERENCE]:
            return MemoryImportance.CRITICAL

        # Actions are high importance
        if memory_type == MemoryType.ACTION:
            return MemoryImportance.HIGH

        # Facts are high importance
        if memory_type == MemoryType.FACT:
            return MemoryImportance.HIGH

        # Errors are medium
        if memory_type == MemoryType.ERROR:
            return MemoryImportance.MEDIUM

        # Check for importance keywords
        content_lower = content.lower()
        
        high_importance_keywords = [
            "важно", "запомни", "всегда", "никогда", "обязательно",
            "important", "remember", "always", "never", "must",
        ]
        
        if any(kw in content_lower for kw in high_importance_keywords):
            return MemoryImportance.HIGH

        # Long conversations are medium importance
        if len(content) > 100:
            return MemoryImportance.MEDIUM

        # Everything else is low
        return MemoryImportance.LOW

    def should_save_to_short_term(
        self,
        importance: MemoryImportance,
    ) -> bool:
        """Check if should save to short-term memory"""
        # All memories go to short-term
        return True

    def should_save_to_long_term(
        self,
        importance: MemoryImportance,
    ) -> bool:
        """Check if should save to long-term memory"""
        # Medium and above go to long-term
        return importance in [
            MemoryImportance.MEDIUM,
            MemoryImportance.HIGH,
            MemoryImportance.CRITICAL,
        ]

    def get_retention_days(
        self,
        importance: MemoryImportance,
    ) -> Optional[int]:
        """
        Get retention period in days
        
        Args:
            importance: Memory importance
            
        Returns:
            Days to keep, or None for indefinite
        """
        return self.RETENTION_POLICY.get(importance)

    def get_expiration_date(
        self,
        importance: MemoryImportance,
        created_at: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """
        Get expiration date for memory
        
        Args:
            importance: Memory importance
            created_at: Creation timestamp
            
        Returns:
            Expiration datetime, or None if never expires
        """
        retention_days = self.get_retention_days(importance)
        
        if retention_days is None:
            return None  # Never expires

        if created_at is None:
            created_at = datetime.utcnow()

        return created_at + timedelta(days=retention_days)

    def should_cleanup(
        self,
        memory: Dict[str, Any],
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Check if memory should be cleaned up
        
        Args:
            memory: Memory dictionary with metadata
            current_time: Current time
            
        Returns:
            True if should be deleted
        """
        if current_time is None:
            current_time = datetime.utcnow()

        # Check expiration
        expires_at = memory.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            
            if current_time >= expires_at:
                return True

        # Never cleanup critical memories
        importance = memory.get("importance")
        if importance == MemoryImportance.CRITICAL:
            return False

        return False

    def classify_content(
        self,
        content: str,
        role: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryType:
        """
        Classify content into memory type
        
        Args:
            content: Content to classify
            role: Message role (user, assistant, system)
            metadata: Optional metadata
            
        Returns:
            Memory type
        """
        content_lower = content.lower()

        # Check for explicit rules
        rule_keywords = ["запомни", "всегда", "никогда", "правило", "remember", "always", "never", "rule"]
        if any(kw in content_lower for kw in rule_keywords):
            return MemoryType.RULE

        # Check for preferences
        preference_keywords = ["предпочитаю", "люблю", "не люблю", "prefer", "like", "dislike"]
        if any(kw in content_lower for kw in preference_keywords):
            return MemoryType.PREFERENCE

        # Check for facts
        fact_keywords = ["это", "такое", "означает", "is", "means", "refers"]
        if any(kw in content_lower for kw in fact_keywords):
            return MemoryType.FACT

        # Check for actions
        if metadata and metadata.get("intent") in ["ha_control", "ha_automation"]:
            return MemoryType.ACTION

        # Check for errors
        if "ошибка" in content_lower or "error" in content_lower:
            return MemoryType.ERROR

        # Default to conversation
        return MemoryType.CONVERSATION


# Global policy instance
memory_policy = MemoryPolicy()
