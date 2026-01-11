"""Pydantic models for the Agent Backend API."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# =============================================================================
# Request Models
# =============================================================================

class JoinRequest(BaseModel):
    """Request to join a negotiation session."""
    session_id: str = Field(..., description="Session ID to join")
    private_info: str = Field(..., description="Agent's private information/constraints")


class TurnRequest(BaseModel):
    """Request from Arena to generate a turn response."""
    session_id: str
    goal: str
    history: list[dict] = Field(default_factory=list)
    turn_number: int


# =============================================================================
# Response Models
# =============================================================================

class JoinResponse(BaseModel):
    """Response after joining a session."""
    agent_id: str = Field(..., description="A or B")
    ready: bool = True


class TurnResponse(BaseModel):
    """Response containing the public message."""
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    agent_id: str


# =============================================================================
# CI Gateway Models
# =============================================================================

class CIGatewayDecision(BaseModel):
    """A single CI Gateway filtering decision."""
    original: str = Field(..., description="Original text that was evaluated")
    action: str = Field(..., description="ALLOW, BLOCK, or TRANSFORM")
    result: Optional[str] = Field(None, description="Transformed text if action is TRANSFORM")
    reason: str = Field(..., description="Why this decision was made")


class CIGatewayLog(BaseModel):
    """Complete CI Gateway log for a turn."""
    decisions: list[CIGatewayDecision] = Field(default_factory=list)
    original_message: str
    filtered_message: str


# =============================================================================
# Audit Trail Models
# =============================================================================

class ThinkingStep(BaseModel):
    """A single step in the agent's thinking process."""
    step: str
    content: str


class BATNAAnalysis(BaseModel):
    """BATNA (Best Alternative to Negotiated Agreement) analysis."""
    batna_value: Optional[float] = Field(None, description="Numerical BATNA value if applicable")
    batna_description: str = Field(..., description="Description of the walk-away point")
    current_offer_acceptable: bool = Field(True, description="Whether current offer beats BATNA")
    reasoning: str


class AuditEntry(BaseModel):
    """A single entry in the audit trail for one turn."""
    turn: int
    timestamp: datetime
    thinking_steps: list[str]
    strategy: str
    batna_analysis: BATNAAnalysis
    ci_gateway_log: CIGatewayLog
    final_message: str


class AuditTrailResponse(BaseModel):
    """Complete audit trail for a session."""
    session_id: str
    agent_id: str
    audit_trail: list[AuditEntry]
