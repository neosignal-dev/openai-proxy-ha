"""Base agent abstract class for LLM interactions"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AgentType(str, Enum):
    """Agent types"""
    TEXT = "text"
    VOICE = "voice"
    REALTIME = "realtime"


class ResponseType(str, Enum):
    """Response types"""
    TEXT = "text"
    AUDIO = "audio"
    ACTION_PLAN = "action_plan"
    FUNCTION_CALL = "function_call"
    STREAM = "stream"


@dataclass
class AgentMessage:
    """Message in agent conversation"""
    role: str  # system, user, assistant, function
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentResponse:
    """Unified agent response"""
    type: ResponseType
    content: str
    audio_data: Optional[bytes] = None
    audio_format: Optional[str] = None
    actions: Optional[List[Dict[str, Any]]] = None
    needs_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None


@dataclass
class AgentContext:
    """Context for agent execution"""
    user_id: str
    session_id: Optional[str] = None
    messages: List[AgentMessage] = field(default_factory=list)
    ha_context: Optional[Dict[str, Any]] = None
    user_rules: List[Dict[str, Any]] = field(default_factory=list)
    relevant_memories: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all LLM agents.
    
    Responsibilities:
    - Define common interface for all agents
    - Handle conversation context
    - Manage session state
    - Provide consistent response format
    """

    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.active_sessions: Dict[str, AgentContext] = {}

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize agent resources (connections, models, etc.)"""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup agent resources"""
        pass

    @abstractmethod
    async def process(
        self,
        context: AgentContext,
        input_text: Optional[str] = None,
        input_audio: Optional[bytes] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentResponse:
        """
        Process input and generate response
        
        Args:
            context: Agent context with conversation history
            input_text: Optional text input
            input_audio: Optional audio input
            tools: Optional tools/functions available to agent
            
        Returns:
            Agent response
        """
        pass

    @abstractmethod
    async def stream_process(
        self,
        context: AgentContext,
        input_text: Optional[str] = None,
        input_audio: Optional[bytes] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[AgentResponse, None]:
        """
        Stream processing for real-time responses
        
        Args:
            context: Agent context
            input_text: Optional text input
            input_audio: Optional audio input
            tools: Optional tools
            
        Yields:
            Partial agent responses
        """
        pass

    def create_session(self, user_id: str, session_id: str) -> AgentContext:
        """Create new agent session
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            New agent context
        """
        context = AgentContext(
            user_id=user_id,
            session_id=session_id,
        )
        self.active_sessions[session_id] = context
        return context

    def get_session(self, session_id: str) -> Optional[AgentContext]:
        """Get existing session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Agent context or None
        """
        return self.active_sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        """Close and cleanup session
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]

    def add_message(
        self,
        context: AgentContext,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add message to conversation context
        
        Args:
            context: Agent context
            role: Message role
            content: Message content
            metadata: Optional metadata
        """
        message = AgentMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        context.messages.append(message)

    def get_conversation_history(
        self,
        context: AgentContext,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get conversation history
        
        Args:
            context: Agent context
            limit: Optional limit on number of messages
            
        Returns:
            List of messages as dictionaries
        """
        messages = context.messages[-limit:] if limit else context.messages
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "metadata": msg.metadata,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in messages
        ]

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check agent health
        
        Returns:
            Health status dictionary
        """
        pass
