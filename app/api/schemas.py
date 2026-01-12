"""Pydantic schemas for API requests and responses"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """Command execution request"""
    user_id: str = Field(..., description="User identifier")
    command: str = Field(..., description="User command")
    include_context: bool = Field(default=True, description="Include HA context")


class CommandResponse(BaseModel):
    """Command execution response"""
    type: str = Field(..., description="Response type (action_plan, text_response)")
    response: str = Field(..., description="Text response")
    intent: Optional[str] = Field(None, description="Detected intent")
    actions: Optional[List[Dict[str, Any]]] = Field(None, description="Actions to execute")
    needs_confirmation: Optional[bool] = Field(None, description="Requires confirmation")
    audio_url: Optional[str] = Field(None, description="URL to audio response")


class ConfirmRequest(BaseModel):
    """Action confirmation request"""
    user_id: str = Field(..., description="User identifier")
    plan: Dict[str, Any] = Field(..., description="Action plan to confirm")
    confirmed: bool = Field(..., description="User confirmation")


class ConfirmResponse(BaseModel):
    """Action confirmation response"""
    success: bool = Field(..., description="Execution success")
    message: str = Field(..., description="Status message")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="Execution results")


class SearchRequest(BaseModel):
    """Perplexity search request"""
    query: str = Field(..., description="Search query")
    recency_days: Optional[int] = Field(None, description="Recency filter in days")
    category: Optional[str] = Field(None, description="Search category")
    max_results: int = Field(default=5, description="Maximum results")


class SearchResponse(BaseModel):
    """Search response"""
    answer: str = Field(..., description="Search answer")
    sources: List[str] = Field(..., description="Source URLs")
    category: str = Field(..., description="Search category")
    recency: Optional[str] = Field(None, description="Applied recency filter")


class HabrSearchRequest(BaseModel):
    """Habr search request"""
    query: Optional[str] = Field(None, description="Search query")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    hubs: Optional[List[str]] = Field(None, description="Filter by hubs")
    days: Optional[int] = Field(None, description="Last N days")
    limit: int = Field(default=10, description="Maximum results")


class HabrSearchResponse(BaseModel):
    """Habr search response"""
    articles: List[Dict[str, Any]] = Field(..., description="List of articles")
    count: int = Field(..., description="Total articles found")


class TelegramSendRequest(BaseModel):
    """Telegram message send request"""
    text: str = Field(..., description="Message text")
    parse_mode: str = Field(default="Markdown", description="Parse mode")


class AutomationDraftRequest(BaseModel):
    """Automation draft request"""
    user_id: str = Field(..., description="User identifier")
    description: str = Field(..., description="Natural language automation description")


class AutomationDraftResponse(BaseModel):
    """Automation draft response"""
    automation: Dict[str, Any] = Field(..., description="Generated automation config")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")


class ContextResponse(BaseModel):
    """HA context response"""
    config: Dict[str, Any] = Field(..., description="HA configuration")
    total_entities: int = Field(..., description="Total entities")
    areas: List[Dict[str, Any]] = Field(..., description="Areas")
    entities_by_domain: Dict[str, List[Dict[str, Any]]] = Field(..., description="Entities by domain")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Application version")
    checks: Dict[str, bool] = Field(..., description="Component health checks")


