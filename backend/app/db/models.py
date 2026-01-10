"""
Pydantic models for data validation and API schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    """Base message model."""

    role: Literal["user", "assistant", "system"]
    content: str


class Message(MessageBase):
    """Message with metadata."""

    id: str = Field(default="")
    conversation_id: str
    agent: str | None = None  # Which agent generated this message
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationBase(BaseModel):
    """Base conversation model."""

    title: str = "New Conversation"


class Conversation(ConversationBase):
    """Conversation with metadata."""

    id: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# API Request/Response Models


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    conversation_id: str
    response: str
    agent_steps: list[dict] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    """Response model for listing conversations."""

    conversations: list[Conversation]


class ConversationDetailResponse(BaseModel):
    """Response model for conversation details."""

    conversation: Conversation
    messages: list[Message]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    mongodb: str
    anthropic: str
    errors: list[str] = Field(default_factory=list)
