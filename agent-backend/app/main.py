"""Agent Backend - FastAPI Application.

This service runs twice: once as Agent A (port 8001) and once as Agent B (port 8002).
Each instance handles one agent's private information and thinking process.
"""
from __future__ import annotations
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from .config import get_settings
from .db import connect_db, close_db, get_db
from .models import (
    JoinRequest,
    JoinResponse,
    TurnRequest,
    TurnResponse,
    HealthResponse,
    AuditTrailResponse,
    AuditEntry,
)
from .agent import process_turn


# =============================================================================
# Session Storage (in-memory, per-agent instance)
# =============================================================================
# Key: session_id -> {"private_info": str, "joined_at": datetime}
sessions: dict[str, dict] = {}


# =============================================================================
# Lifespan Management
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    settings = get_settings()

    print(f"\n{'='*60}")
    print(f"  AGENT {settings.agent_id} BACKEND")
    print(f"  Port: {settings.port}")
    print(f"  Arena URL: {settings.arena_url}")
    print(f"{'='*60}\n")

    # Validate configuration
    errors = settings.validate_config()
    if errors:
        for error in errors:
            print(f"  [WARNING] {error}")
    else:
        print("  [OK] Configuration validated")

    # Connect to MongoDB (non-blocking)
    await connect_db()
    print(f"  [OK] MongoDB initialized (collection: {settings.audit_collection})")

    yield

    # Cleanup
    await close_db()
    print(f"\nAgent {settings.agent_id} Backend shutdown complete")


# =============================================================================
# FastAPI App
# =============================================================================
app = FastAPI(
    title="Agent Backend",
    description="Privacy-preserving agent backend for negotiation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        agent_id=settings.agent_id
    )


@app.post("/api/join", response_model=JoinResponse)
async def join_session(request: JoinRequest):
    """
    Join a negotiation session with private information.
    Called by the agent's frontend when user submits their private constraints.
    """
    settings = get_settings()

    # Store private info for this session
    sessions[request.session_id] = {
        "private_info": request.private_info,
        "joined_at": datetime.utcnow()
    }

    print(f"[Agent {settings.agent_id}] Joined session {request.session_id}")

    # Notify Arena that this agent is ready
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.arena_url}/api/session/{request.session_id}/agent-ready",
                json={"agent_id": settings.agent_id},
                timeout=10.0
            )
        print(f"[Agent {settings.agent_id}] Notified Arena of readiness")
    except Exception as e:
        print(f"[Agent {settings.agent_id}] Warning: Could not notify Arena: {e}")
        # Don't fail - Arena might not be ready yet

    return JoinResponse(
        agent_id=settings.agent_id,
        ready=True
    )


@app.post("/api/turn", response_model=TurnResponse)
async def handle_turn(request: TurnRequest):
    """
    Handle a negotiation turn.
    Called by Arena to get this agent's response.
    """
    settings = get_settings()

    # Get session data
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {request.session_id} not found. Agent must join first."
        )

    print(f"[Agent {settings.agent_id}] Processing turn {request.turn_number} for session {request.session_id}")

    # Get database
    db = get_db()

    # Process the turn
    try:
        message, audit_entry = await process_turn(
            session_id=request.session_id,
            goal=request.goal,
            history=request.history,
            turn_number=request.turn_number,
            private_info=session["private_info"],
            agent_id=settings.agent_id,
            db=db
        )

        print(f"[Agent {settings.agent_id}] Turn {request.turn_number} complete. Strategy: {audit_entry.strategy}")

        return TurnResponse(message=message)

    except Exception as e:
        print(f"[Agent {settings.agent_id}] Error processing turn: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing turn: {str(e)}"
        )


@app.get("/api/audit/{session_id}", response_model=AuditTrailResponse)
async def get_audit_trail(session_id: str):
    """
    Get the audit trail for a session.
    Called by the agent's frontend to display thinking steps.
    """
    settings = get_settings()
    db = get_db()

    # Fetch audit entries from MongoDB
    cursor = db[settings.audit_collection].find(
        {"session_id": session_id}
    ).sort("turn", 1)

    entries = []
    async for doc in cursor:
        # Convert MongoDB document to AuditEntry
        batna_data = doc.get("batna_analysis", {})
        ci_data = doc.get("ci_gateway_log", {})

        from .models import BATNAAnalysis, CIGatewayLog, CIGatewayDecision

        entries.append(AuditEntry(
            turn=doc["turn"],
            timestamp=doc["timestamp"],
            thinking_steps=doc.get("thinking_steps", []),
            strategy=doc.get("strategy", "Unknown"),
            batna_analysis=BATNAAnalysis(
                batna_value=batna_data.get("batna_value"),
                batna_description=batna_data.get("batna_description", ""),
                current_offer_acceptable=batna_data.get("current_offer_acceptable", True),
                reasoning=batna_data.get("reasoning", "")
            ),
            ci_gateway_log=CIGatewayLog(
                original_message=ci_data.get("original_message", ""),
                filtered_message=ci_data.get("filtered_message", ""),
                decisions=[
                    CIGatewayDecision(
                        original=d.get("original", ""),
                        action=d.get("action", "ALLOW"),
                        result=d.get("result"),
                        reason=d.get("reason", "")
                    )
                    for d in ci_data.get("decisions", [])
                ]
            ),
            final_message=doc.get("final_message", "")
        ))

    return AuditTrailResponse(
        session_id=session_id,
        agent_id=settings.agent_id,
        audit_trail=entries
    )


@app.get("/")
async def root():
    """Root endpoint."""
    settings = get_settings()
    return {
        "service": f"Agent {settings.agent_id} Backend",
        "status": "running",
        "endpoints": {
            "health": "/api/health",
            "join": "/api/join",
            "turn": "/api/turn",
            "audit": "/api/audit/{session_id}"
        }
    }
