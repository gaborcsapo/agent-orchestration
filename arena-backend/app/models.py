"""Pydantic models for the Arena Backend API."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class SessionStatus(str, Enum):
    WAITING = "waiting"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    CONSENSUS = "consensus"
    DEADLOCK = "deadlock"


# =============================================================================
# Request Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new negotiation session."""
    goal: str = Field(..., description="The negotiation goal")


class AgentReadyRequest(BaseModel):
    """Notification that an agent is ready."""
    agent_id: str = Field(..., description="A or B")


# =============================================================================
# Response Models
# =============================================================================

class CreateSessionResponse(BaseModel):
    """Response after creating a session."""
    session_id: str
    status: SessionStatus = SessionStatus.WAITING


class SessionStatusResponse(BaseModel):
    """Current status of a session."""
    session_id: str
    goal: str
    agent_a_ready: bool = False
    agent_b_ready: bool = False
    status: SessionStatus
    current_turn: int = 0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    services: dict[str, str]


# =============================================================================
# Judge Models
# =============================================================================

class JudgeEvaluation(BaseModel):
    """Judge's evaluation of a turn."""
    progress: bool = Field(..., description="Whether progress was made")
    progress_score: int = Field(..., ge=0, le=10, description="Progress toward agreement (0-10)")
    is_deadlock: bool = Field(False, description="Whether negotiation has deadlocked")
    is_consensus: bool = Field(False, description="Whether consensus was reached")
    reasoning: str = Field(..., description="Judge's reasoning")
    consensus_summary: Optional[str] = Field(None, description="Summary of agreement if consensus")


# =============================================================================
# Turn Models
# =============================================================================

class TurnData(BaseModel):
    """Data for a single negotiation turn."""
    turn: int
    agent_a_message: str
    agent_b_message: str
    judge: JudgeEvaluation
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionHistory(BaseModel):
    """Complete session history."""
    session_id: str
    goal: str
    turns: list[TurnData]
    status: SessionStatus
    final_conclusion: Optional[str] = None


# =============================================================================
# SSE Event Models
# =============================================================================

class TurnEvent(BaseModel):
    """SSE event for a turn completion."""
    type: str = "turn"
    turn: int
    agent_a_message: str
    agent_b_message: str
    judge: JudgeEvaluation


class CompleteEvent(BaseModel):
    """SSE event for negotiation completion."""
    type: str = "complete"
    status: str
    conclusion: str
