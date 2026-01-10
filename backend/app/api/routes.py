"""
API Routes for the Agent Negotiation System.

Endpoints:
- POST /api/negotiate/start: Start a new negotiation session
- POST /api/negotiate/step: Execute one round of negotiation
- POST /api/negotiate/run: Run a full negotiation until completion
- GET /api/negotiate/status/{session_id}: Get negotiation status
- GET /api/health: Health check endpoint
"""

from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import asyncio

from app.db.models import (
    StartNegotiationRequest,
    StartNegotiationResponse,
    StepNegotiationRequest,
    StepNegotiationResponse,
    NegotiationStatusResponse,
    RunFullNegotiationRequest,
    RunFullNegotiationResponse,
    NegotiationTurn,
    JudgeEvaluation,
    HealthResponse,
)
from app.agents import run_negotiation_turn, run_full_negotiation
from app.core.config import get_settings

router = APIRouter(prefix="/api")

# In-memory session storage
_sessions: dict[str, dict] = {}


# =============================================================================
# Negotiation Endpoints
# =============================================================================


@router.post("/negotiate/start", response_model=StartNegotiationResponse)
async def start_negotiation(request: StartNegotiationRequest):
    """
    Start a new negotiation session.
    Returns a session_id that can be used for step-by-step negotiation.
    """
    session_id = str(uuid4())

    # Initialize session state
    _sessions[session_id] = {
        "goal": request.goal,
        "agent_a_info": request.agent_a_info,
        "agent_b_info": request.agent_b_info,
        "negotiation_history": [],
        "current_turn": 0,
        "status": "in_progress",
        "agent_a_response": "",
        "agent_b_response": "",
        "judge_evaluation": {},
        "final_conclusion": None,
        "progress_score": 0,
        "deadlock_counter": 0,
    }

    return StartNegotiationResponse(
        session_id=session_id,
        status="in_progress",
        message="Negotiation session created. Use /negotiate/step to proceed.",
    )


@router.post("/negotiate/step", response_model=StepNegotiationResponse)
async def step_negotiation(request: StepNegotiationRequest):
    """
    Execute one round of negotiation.
    Agent A speaks, Agent B responds, Judge evaluates.
    """
    session_id = request.session_id

    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _sessions[session_id]

    if state["status"] != "in_progress":
        raise HTTPException(
            status_code=400,
            detail=f"Negotiation already ended with status: {state['status']}",
        )

    try:
        # Run one turn of negotiation
        updated_state = await run_negotiation_turn(state)
        _sessions[session_id] = updated_state

        # Build response
        judge_eval = updated_state["judge_evaluation"]

        return StepNegotiationResponse(
            session_id=session_id,
            turn=updated_state["current_turn"],
            agent_a_response=updated_state["agent_a_response"],
            agent_b_response=updated_state["agent_b_response"],
            judge_evaluation=JudgeEvaluation(
                progress=judge_eval.get("progress", True),
                progress_score=judge_eval.get("progress_score", 5),
                is_deadlock=judge_eval.get("is_deadlock", False),
                is_consensus=judge_eval.get("is_consensus", False),
                reasoning=judge_eval.get("reasoning", ""),
                consensus_summary=judge_eval.get("consensus_summary"),
            ),
            status=updated_state["status"],
            final_conclusion=updated_state["final_conclusion"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Negotiation step failed: {str(e)}"
        )


@router.post("/negotiate/run", response_model=RunFullNegotiationResponse)
async def run_negotiation(request: RunFullNegotiationRequest):
    """
    Run a complete negotiation until consensus or deadlock.
    This is a blocking call that returns when the negotiation ends.
    """
    try:
        final_state = await run_full_negotiation(
            goal=request.goal,
            agent_a_info=request.agent_a_info,
            agent_b_info=request.agent_b_info,
        )

        # Convert history to turns format
        turns = []
        history = final_state["negotiation_history"]

        # History is stored as [Agent A msg, Agent B msg, Agent A msg, Agent B msg, ...]
        # We need to pair them up into turns
        for i in range(0, len(history), 2):
            if i + 1 < len(history):
                turn_num = (i // 2) + 1
                turns.append(
                    NegotiationTurn(
                        turn_number=turn_num,
                        agent_a_response=history[i]["message"],
                        agent_b_response=history[i + 1]["message"],
                        judge_evaluation=JudgeEvaluation(
                            progress=True,
                            progress_score=final_state["progress_score"],
                            is_deadlock=final_state["status"] == "deadlock",
                            is_consensus=final_state["status"] == "consensus",
                            reasoning="",
                            consensus_summary=final_state["final_conclusion"]
                            if final_state["status"] == "consensus"
                            else None,
                        ),
                    )
                )

        return RunFullNegotiationResponse(
            session_id=str(uuid4()),
            goal=request.goal,
            status=final_state["status"],
            turns=turns,
            final_conclusion=final_state["final_conclusion"],
            total_turns=final_state["current_turn"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Negotiation failed: {str(e)}"
        )


@router.post("/negotiate/stream")
async def stream_negotiation(request: RunFullNegotiationRequest):
    """
    Stream a negotiation turn by turn using Server-Sent Events.
    Each turn is sent as a JSON event as it completes.
    """

    async def generate():
        settings = get_settings()

        state = {
            "goal": request.goal,
            "agent_a_info": request.agent_a_info,
            "agent_b_info": request.agent_b_info,
            "negotiation_history": [],
            "current_turn": 0,
            "status": "in_progress",
            "agent_a_response": "",
            "agent_b_response": "",
            "judge_evaluation": {},
            "final_conclusion": None,
            "progress_score": 0,
            "deadlock_counter": 0,
        }

        while (
            state["status"] == "in_progress"
            and state["current_turn"] < settings.max_negotiation_turns
        ):
            try:
                state = await run_negotiation_turn(state)

                # Send turn data
                turn_data = {
                    "type": "turn",
                    "turn": state["current_turn"],
                    "agent_a_response": state["agent_a_response"],
                    "agent_b_response": state["agent_b_response"],
                    "judge_evaluation": state["judge_evaluation"],
                    "status": state["status"],
                    "progress_score": state["progress_score"],
                }

                yield f"data: {json.dumps(turn_data)}\n\n"

                # Small delay between turns for readability
                await asyncio.sleep(0.1)

            except Exception as e:
                error_data = {"type": "error", "message": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
                break

        # Send final conclusion
        if state["status"] == "in_progress":
            state["status"] = "deadlock"
            state[
                "final_conclusion"
            ] = f"Negotiation ended after reaching maximum {settings.max_negotiation_turns} turns."

        final_data = {
            "type": "complete",
            "status": state["status"],
            "final_conclusion": state["final_conclusion"],
            "total_turns": state["current_turn"],
        }
        yield f"data: {json.dumps(final_data)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/negotiate/status/{session_id}", response_model=NegotiationStatusResponse)
async def get_negotiation_status(session_id: str):
    """Get the current status of a negotiation session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _sessions[session_id]
    history = state["negotiation_history"]

    # Convert history to turns
    turns = []
    for i in range(0, len(history), 2):
        if i + 1 < len(history):
            turn_num = (i // 2) + 1
            turns.append(
                NegotiationTurn(
                    turn_number=turn_num,
                    agent_a_response=history[i]["message"],
                    agent_b_response=history[i + 1]["message"],
                    judge_evaluation=JudgeEvaluation(
                        progress=True,
                        progress_score=state["progress_score"],
                        is_deadlock=False,
                        is_consensus=False,
                        reasoning="",
                        consensus_summary=None,
                    ),
                )
            )

    return NegotiationStatusResponse(
        session_id=session_id,
        goal=state["goal"],
        status=state["status"],
        current_turn=state["current_turn"],
        turns=turns,
        final_conclusion=state["final_conclusion"],
        progress_score=state["progress_score"],
    )


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check the health of all services.
    """
    settings = get_settings()
    errors = settings.validate_config()

    # Check Anthropic
    anthropic_status = "not_configured"
    if (
        settings.anthropic_api_key
        and settings.anthropic_api_key != "your-anthropic-api-key-here"
    ):
        anthropic_status = "configured"

    overall_status = "healthy" if not errors else "unhealthy"

    return HealthResponse(
        status=overall_status,
        anthropic=anthropic_status,
        errors=errors,
    )
