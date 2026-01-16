"""Arena Backend - FastAPI Application.

This service orchestrates negotiations between Agent A and Agent B.
It manages sessions, coordinates turns, runs the Judge, and streams results.
"""
from __future__ import annotations
import uuid
import asyncio
import json
import httpx
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .config import get_settings
from .db import connect_db, close_db, get_db
from .models import (
    CreateSessionRequest,
    CreateSessionResponse,
    AgentReadyRequest,
    SessionStatusResponse,
    SessionStatus,
    HealthResponse,
    TurnData,
    SessionHistory,
    JudgeEvaluation,
)
from .judge import evaluate_turn


# =============================================================================
# Session Storage
# =============================================================================
# Key: session_id -> session data
sessions: dict[str, dict] = {}

# SSE event queues for each session
event_queues: dict[str, list[asyncio.Queue]] = {}


# =============================================================================
# Lifespan Management
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    settings = get_settings()

    print(f"\n{'='*60}")
    print(f"  ARENA BACKEND")
    print(f"  Port: {settings.port}")
    print(f"  Agent A: {settings.agent_a_url}")
    print(f"  Agent B: {settings.agent_b_url}")
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
    print("  [OK] MongoDB initialized")

    yield

    # Cleanup
    await close_db()
    print("\nArena Backend shutdown complete")


# =============================================================================
# FastAPI App
# =============================================================================
app = FastAPI(
    title="Arena Backend",
    description="Negotiation orchestration service",
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
# Helper Functions
# =============================================================================

async def broadcast_event(session_id: str, event: dict):
    """Broadcast an event to all SSE listeners for a session."""
    if session_id in event_queues:
        for queue in event_queues[session_id]:
            await queue.put(event)


async def call_agent(agent_url: str, session_id: str, goal: str, history: list, turn_number: int) -> str:
    """Call an agent backend to get their response."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{agent_url}/api/turn",
            json={
                "session_id": session_id,
                "goal": goal,
                "history": history,
                "turn_number": turn_number
            },
            timeout=60.0  # LLM calls can take time
        )
        response.raise_for_status()
        return response.json()["message"]


async def safe_db_operation(operation, description: str):
    """Execute a database operation, logging errors but not failing."""
    try:
        await operation
    except Exception as e:
        print(f"[Arena] MongoDB {description} skipped: {e}")


async def run_negotiation(session_id: str):
    """Main negotiation loop."""
    settings = get_settings()
    session = sessions[session_id]
    db = get_db()

    print(f"\n[Arena] Starting negotiation for session {session_id}")

    # Build history format for agents (list of {agent, message})
    agent_history = []

    for turn in range(1, settings.max_turns + 1):
        session["current_turn"] = turn
        session["status"] = SessionStatus.IN_PROGRESS

        print(f"[Arena] Turn {turn} starting...")

        try:
            # Get Agent A's response
            print(f"[Arena] Calling Agent A...")
            agent_a_message = await call_agent(
                agent_url=settings.agent_a_url,
                session_id=session_id,
                goal=session["goal"],
                history=agent_history,
                turn_number=turn
            )
            print(f"[Arena] Agent A responded: {agent_a_message[:100]}...")

            # Update history for Agent B (include A's message)
            history_for_b = agent_history + [{"agent": "Partner A", "message": agent_a_message}]

            # Get Agent B's response
            print(f"[Arena] Calling Agent B...")
            agent_b_message = await call_agent(
                agent_url=settings.agent_b_url,
                session_id=session_id,
                goal=session["goal"],
                history=history_for_b,
                turn_number=turn
            )
            print(f"[Arena] Agent B responded: {agent_b_message[:100]}...")

            # Update full history
            agent_history.append({"agent": "Partner A", "message": agent_a_message})
            agent_history.append({"agent": "Partner B", "message": agent_b_message})

            # Run Judge evaluation
            print(f"[Arena] Running Judge evaluation...")
            judge_result = await evaluate_turn(
                goal=session["goal"],
                history=session["turns"],
                agent_a_message=agent_a_message,
                agent_b_message=agent_b_message,
                turn_number=turn
            )
            print(f"[Arena] Judge: progress={judge_result.progress}, score={judge_result.progress_score}, consensus={judge_result.is_consensus}")

            # Create turn data
            turn_data = TurnData(
                turn=turn,
                agent_a_message=agent_a_message,
                agent_b_message=agent_b_message,
                judge=judge_result,
                timestamp=datetime.utcnow()
            )

            # Store turn
            session["turns"].append(turn_data)

            # Update MongoDB (optional)
            await safe_db_operation(
                db["public_sessions"].update_one(
                    {"session_id": session_id},
                    {
                        "$push": {"turns": turn_data.model_dump()},
                        "$set": {"current_turn": turn, "status": session["status"].value}
                    }
                ),
                "turn update"
            )

            # Broadcast turn event via SSE
            await broadcast_event(session_id, {
                "type": "turn",
                "turn": turn,
                "agent_a_message": agent_a_message,
                "agent_b_message": agent_b_message,
                "judge": judge_result.model_dump()
            })

            # Check for completion
            if judge_result.is_consensus:
                session["status"] = SessionStatus.CONSENSUS
                session["final_conclusion"] = judge_result.consensus_summary or "Agreement reached"
                print(f"[Arena] CONSENSUS REACHED: {session['final_conclusion']}")

                await safe_db_operation(
                    db["public_sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "status": "consensus",
                            "final_conclusion": session["final_conclusion"]
                        }}
                    ),
                    "consensus update"
                )

                await broadcast_event(session_id, {
                    "type": "complete",
                    "status": "consensus",
                    "conclusion": session["final_conclusion"]
                })
                return

            if judge_result.is_deadlock:
                session["status"] = SessionStatus.DEADLOCK
                session["final_conclusion"] = "Negotiation reached deadlock - parties unable to agree"
                print(f"[Arena] DEADLOCK DETECTED")

                await safe_db_operation(
                    db["public_sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "status": "deadlock",
                            "final_conclusion": session["final_conclusion"]
                        }}
                    ),
                    "deadlock update"
                )

                await broadcast_event(session_id, {
                    "type": "complete",
                    "status": "deadlock",
                    "conclusion": session["final_conclusion"]
                })
                return

        except Exception as e:
            print(f"[Arena] Error in turn {turn}: {e}")
            await broadcast_event(session_id, {
                "type": "error",
                "message": str(e)
            })
            raise

    # Max turns reached without conclusion
    session["status"] = SessionStatus.DEADLOCK
    session["final_conclusion"] = f"Negotiation ended after {settings.max_turns} turns without agreement"

    await safe_db_operation(
        db["public_sessions"].update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "deadlock",
                "final_conclusion": session["final_conclusion"]
            }}
        ),
        "max turns update"
    )

    await broadcast_event(session_id, {
        "type": "complete",
        "status": "deadlock",
        "conclusion": session["final_conclusion"]
    })


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    settings = get_settings()

    # Check agent backends
    services = {"arena": "ok"}

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{settings.agent_a_url}/api/health", timeout=5.0)
            services["agent_a"] = "ok" if r.status_code == 200 else "error"
        except Exception:
            services["agent_a"] = "unreachable"

        try:
            r = await client.get(f"{settings.agent_b_url}/api/health", timeout=5.0)
            services["agent_b"] = "ok" if r.status_code == 200 else "error"
        except Exception:
            services["agent_b"] = "unreachable"

    return HealthResponse(
        status="ok" if all(v == "ok" for v in services.values()) else "degraded",
        services=services
    )


@app.post("/api/session/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new negotiation session."""
    session_id = str(uuid.uuid4())[:8]

    sessions[session_id] = {
        "goal": request.goal,
        "agent_a_ready": False,
        "agent_b_ready": False,
        "status": SessionStatus.WAITING,
        "turns": [],
        "current_turn": 0,
        "final_conclusion": None,
        "created_at": datetime.utcnow()
    }

    # Store in MongoDB (optional - don't fail if unavailable)
    try:
        db = get_db()
        await db["public_sessions"].insert_one({
            "session_id": session_id,
            "goal": request.goal,
            "status": "waiting",
            "turns": [],
            "current_turn": 0,
            "created_at": datetime.utcnow()
        })
    except Exception as e:
        print(f"[Arena] MongoDB write skipped (not available): {e}")

    # Initialize event queue list
    event_queues[session_id] = []

    print(f"[Arena] Created session {session_id}: {request.goal[:50]}...")

    return CreateSessionResponse(
        session_id=session_id,
        status=SessionStatus.WAITING
    )


@app.post("/api/session/{session_id}/agent-ready")
async def agent_ready(session_id: str, request: AgentReadyRequest):
    """Called by agent backends when they join a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    if request.agent_id == "A":
        session["agent_a_ready"] = True
        print(f"[Arena] Agent A ready for session {session_id}")
    elif request.agent_id == "B":
        session["agent_b_ready"] = True
        print(f"[Arena] Agent B ready for session {session_id}")
    else:
        raise HTTPException(status_code=400, detail="Invalid agent_id")

    # Check if both are ready
    if session["agent_a_ready"] and session["agent_b_ready"]:
        session["status"] = SessionStatus.READY
        print(f"[Arena] Session {session_id} ready to start!")

    # Broadcast status update
    await broadcast_event(session_id, {
        "type": "status",
        "agent_a_ready": session["agent_a_ready"],
        "agent_b_ready": session["agent_b_ready"],
        "status": session["status"].value
    })

    return {"status": session["status"].value}


@app.get("/api/session/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """Get current session status."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    return SessionStatusResponse(
        session_id=session_id,
        goal=session["goal"],
        agent_a_ready=session["agent_a_ready"],
        agent_b_ready=session["agent_b_ready"],
        status=session["status"],
        current_turn=session["current_turn"]
    )


@app.post("/api/session/{session_id}/start")
async def start_negotiation(session_id: str, background_tasks: BackgroundTasks):
    """Start the negotiation (must have both agents ready)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    if session["status"] != SessionStatus.READY:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start: status is {session['status'].value}, need 'ready'"
        )

    session["status"] = SessionStatus.IN_PROGRESS

    # Run negotiation in background
    background_tasks.add_task(run_negotiation, session_id)

    return {"status": "started", "session_id": session_id}


@app.get("/api/session/{session_id}/stream")
async def stream_events(session_id: str):
    """SSE endpoint for real-time updates."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator() -> AsyncGenerator[dict, None]:
        queue: asyncio.Queue = asyncio.Queue()

        # Register this client's queue
        if session_id not in event_queues:
            event_queues[session_id] = []
        event_queues[session_id].append(queue)

        try:
            # Send current status immediately
            session = sessions[session_id]
            yield {
                "event": "status",
                "data": json.dumps({
                    "type": "status",
                    "agent_a_ready": session["agent_a_ready"],
                    "agent_b_ready": session["agent_b_ready"],
                    "status": session["status"].value,
                    "current_turn": session["current_turn"]
                })
            }

            # Send existing turns
            for turn_data in session["turns"]:
                yield {
                    "event": "turn",
                    "data": json.dumps({
                        "type": "turn",
                        "turn": turn_data.turn,
                        "agent_a_message": turn_data.agent_a_message,
                        "agent_b_message": turn_data.agent_b_message,
                        "judge": turn_data.judge.model_dump()
                    })
                }

            # Stream new events
            while True:
                event = await queue.get()
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event)
                }

                # Stop streaming on completion
                if event.get("type") in ["complete", "error"]:
                    break

        finally:
            # Unregister queue
            if session_id in event_queues and queue in event_queues[session_id]:
                event_queues[session_id].remove(queue)

    return EventSourceResponse(event_generator())


@app.get("/api/session/{session_id}/history", response_model=SessionHistory)
async def get_session_history(session_id: str):
    """Get complete session history."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    return SessionHistory(
        session_id=session_id,
        goal=session["goal"],
        turns=session["turns"],
        status=session["status"],
        final_conclusion=session.get("final_conclusion")
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Arena Backend",
        "status": "running",
        "endpoints": {
            "health": "/api/health",
            "create_session": "/api/session/create",
            "session_status": "/api/session/{session_id}/status",
            "start": "/api/session/{session_id}/start",
            "stream": "/api/session/{session_id}/stream",
            "history": "/api/session/{session_id}/history"
        }
    }
