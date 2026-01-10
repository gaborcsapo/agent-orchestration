"""
Pydantic models for the Negotiation System.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# =============================================================================
# Negotiation Models
# =============================================================================


class NegotiationTurn(BaseModel):
    """A single turn in the negotiation."""
    turn_number: int
    agent_a_response: str
    agent_b_response: str
    judge_evaluation: "JudgeEvaluation"


class JudgeEvaluation(BaseModel):
    """Judge's evaluation of a negotiation turn."""
    progress: bool
    progress_score: int = Field(ge=0, le=10)
    is_deadlock: bool = False
    is_consensus: bool = False
    reasoning: str
    consensus_summary: str | None = None


class NegotiationState(BaseModel):
    """Complete state of a negotiation session."""
    session_id: str
    goal: str
    agent_a_info: str
    agent_b_info: str
    status: Literal["in_progress", "deadlock", "consensus"] = "in_progress"
    current_turn: int = 0
    turns: list[NegotiationTurn] = Field(default_factory=list)
    final_conclusion: str | None = None
    progress_score: int = 0
    deadlock_counter: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# API Request/Response Models
# =============================================================================


class StartNegotiationRequest(BaseModel):
    """Request to start a new negotiation."""
    goal: str = Field(..., description="The objective both agents must reach")
    agent_a_info: str = Field(..., description="Private information for Agent A")
    agent_b_info: str = Field(..., description="Private information for Agent B")


class StartNegotiationResponse(BaseModel):
    """Response after starting a negotiation."""
    session_id: str
    status: str
    message: str


class StepNegotiationRequest(BaseModel):
    """Request to execute one negotiation step."""
    session_id: str


class StepNegotiationResponse(BaseModel):
    """Response after executing a negotiation step."""
    session_id: str
    turn: int
    agent_a_response: str
    agent_b_response: str
    judge_evaluation: JudgeEvaluation
    status: Literal["in_progress", "deadlock", "consensus"]
    final_conclusion: str | None = None


class NegotiationStatusResponse(BaseModel):
    """Full status of a negotiation session."""
    session_id: str
    goal: str
    status: Literal["in_progress", "deadlock", "consensus"]
    current_turn: int
    turns: list[NegotiationTurn]
    final_conclusion: str | None = None
    progress_score: int


class RunFullNegotiationRequest(BaseModel):
    """Request to run a full negotiation until completion."""
    goal: str = Field(..., description="The objective both agents must reach")
    agent_a_info: str = Field(..., description="Private information for Agent A")
    agent_b_info: str = Field(..., description="Private information for Agent B")


class RunFullNegotiationResponse(BaseModel):
    """Response with the complete negotiation result."""
    session_id: str
    goal: str
    status: Literal["in_progress", "deadlock", "consensus"]
    turns: list[NegotiationTurn]
    final_conclusion: str | None
    total_turns: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    anthropic: str
    errors: list[str] = Field(default_factory=list)
