"""
LangGraph Multi-Agent Negotiation Workflow

This module defines a three-agent negotiation system:
- Agent A: First negotiator with private information
- Agent B: Second negotiator with private information
- Judge: Evaluates progress, detects deadlock or consensus

The workflow implements turn-based negotiation where:
1. Agent A makes a statement/proposal
2. Agent B responds
3. Judge evaluates the exchange
4. Loop continues until consensus or deadlock
"""
from __future__ import annotations

import json
import re
from typing import TypedDict, Literal
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_settings


# =============================================================================
# State Definition
# =============================================================================


class NegotiationAgentState(TypedDict):
    """
    State that flows through the negotiation graph.
    """
    goal: str
    agent_a_info: str
    agent_b_info: str
    negotiation_history: list[dict]  # List of {speaker, message}
    current_turn: int
    status: Literal["in_progress", "deadlock", "consensus"]
    agent_a_response: str
    agent_b_response: str
    judge_evaluation: dict
    final_conclusion: str | None
    progress_score: int
    deadlock_counter: int


# =============================================================================
# LLM Configuration
# =============================================================================


def get_llm():
    """Get configured LLM instance."""
    settings = get_settings()
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",  # Fast and cost-effective
        api_key=settings.anthropic_api_key,
        temperature=0.7,
    )


# =============================================================================
# Agent Nodes
# =============================================================================


def agent_a_node(state: NegotiationAgentState) -> dict:
    """
    Agent A: First negotiator.
    Has access to their private information and the negotiation history.
    """
    llm = get_llm()

    # Build conversation history for context
    history_text = ""
    if state["negotiation_history"]:
        for entry in state["negotiation_history"]:
            history_text += f"\n{entry['speaker']}: {entry['message']}"

    system_prompt = f"""You are Agent A in a negotiation. Your objective is to work toward this goal:
"{state['goal']}"

YOUR PRIVATE INFORMATION (ONLY YOU HAVE ACCESS TO THIS - DO NOT REVEAL DIRECTLY):
{state['agent_a_info']}

IMPORTANT GUIDELINES:
- Work toward reaching the shared goal with Agent B
- Use your private information to guide your strategy, but don't reveal it directly
- Be strategic but collaborative - the goal is to find common ground
- Make concrete proposals or counter-proposals
- Be concise and clear in your communication
- If you believe an agreement has been reached, clearly state what you're agreeing to

This is turn {state['current_turn'] + 1} of the negotiation."""

    user_message = "Begin the negotiation with your opening statement or proposal."
    if history_text:
        user_message = f"""Negotiation history so far:{history_text}

Based on the conversation above, provide your next statement or counter-proposal. Be direct and work toward agreement."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)

    return {
        "agent_a_response": response.content,
    }


def agent_b_node(state: NegotiationAgentState) -> dict:
    """
    Agent B: Second negotiator.
    Has access to their private information and the negotiation history including Agent A's latest response.
    """
    llm = get_llm()

    # Build conversation history including Agent A's latest response
    history_text = ""
    if state["negotiation_history"]:
        for entry in state["negotiation_history"]:
            history_text += f"\n{entry['speaker']}: {entry['message']}"

    # Add Agent A's current response
    history_text += f"\nAgent A: {state['agent_a_response']}"

    system_prompt = f"""You are Agent B in a negotiation. Your objective is to work toward this goal:
"{state['goal']}"

YOUR PRIVATE INFORMATION (ONLY YOU HAVE ACCESS TO THIS - DO NOT REVEAL DIRECTLY):
{state['agent_b_info']}

IMPORTANT GUIDELINES:
- Work toward reaching the shared goal with Agent A
- Use your private information to guide your strategy, but don't reveal it directly
- Be strategic but collaborative - the goal is to find common ground
- Make concrete proposals or counter-proposals
- Be concise and clear in your communication
- If you accept Agent A's proposal or want to make a counter-offer, be explicit
- If you believe an agreement has been reached, clearly state what you're agreeing to

This is turn {state['current_turn'] + 1} of the negotiation."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"""Negotiation history so far:{history_text}

Based on Agent A's statement above, provide your response. Be direct and work toward agreement."""),
    ]

    response = llm.invoke(messages)

    return {
        "agent_b_response": response.content,
    }


def judge_node(state: NegotiationAgentState) -> dict:
    """
    Judge: Evaluates the negotiation progress.
    Does NOT have access to private information, only the goal and public statements.
    """
    llm = get_llm()
    settings = get_settings()

    # Build full conversation history including current turn
    history_text = ""
    if state["negotiation_history"]:
        for entry in state["negotiation_history"]:
            history_text += f"\n{entry['speaker']}: {entry['message']}"

    # Add current turn
    history_text += f"\nAgent A: {state['agent_a_response']}"
    history_text += f"\nAgent B: {state['agent_b_response']}"

    system_prompt = f"""You are an impartial Judge evaluating a negotiation between Agent A and Agent B.

THE NEGOTIATION GOAL:
"{state['goal']}"

IMPORTANT: You do NOT have access to either agent's private information. You can only evaluate based on what has been said publicly.

Your task is to evaluate the current state of the negotiation and determine:
1. Are the agents making progress toward the goal? (progress: true/false)
2. What is the current progress score? (0-10, where 10 = very close to agreement)
3. Is there a deadlock? (No movement, positions entrenched, same arguments repeated)
4. Has consensus been reached? (Both agents explicitly agreed on a specific solution)

DEADLOCK CRITERIA:
- Same positions repeated without new proposals
- Explicit refusal to compromise from both sides
- No movement for multiple turns
- Current deadlock counter: {state['deadlock_counter']} (threshold: {settings.deadlock_threshold})

CONSENSUS CRITERIA:
- Both agents explicitly agree to specific terms
- The agreement addresses the stated goal
- No outstanding objections or conditions

You MUST respond with ONLY a valid JSON object (no other text before or after), following this exact format:
{{
    "progress": true or false,
    "progress_score": number from 0 to 10,
    "is_deadlock": true or false,
    "is_consensus": true or false,
    "reasoning": "Your brief explanation",
    "consensus_summary": "If consensus reached, summarize the agreement here, otherwise null"
}}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"""Negotiation history:{history_text}

This is turn {state['current_turn'] + 1}. Evaluate the negotiation state and respond with ONLY the JSON object."""),
    ]

    response = llm.invoke(messages)

    # Parse the JSON response
    try:
        # Try to extract JSON from the response
        content = response.content.strip()
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        evaluation = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        # Default evaluation if parsing fails
        evaluation = {
            "progress": True,
            "progress_score": 5,
            "is_deadlock": False,
            "is_consensus": False,
            "reasoning": "Unable to parse evaluation, continuing negotiation.",
            "consensus_summary": None
        }

    # Ensure all required fields exist
    evaluation.setdefault("progress", True)
    evaluation.setdefault("progress_score", 5)
    evaluation.setdefault("is_deadlock", False)
    evaluation.setdefault("is_consensus", False)
    evaluation.setdefault("reasoning", "")
    evaluation.setdefault("consensus_summary", None)

    # Update deadlock counter
    new_deadlock_counter = state["deadlock_counter"]
    if not evaluation["progress"]:
        new_deadlock_counter += 1
    else:
        new_deadlock_counter = 0  # Reset on progress

    # Determine final status
    new_status = state["status"]
    final_conclusion = state["final_conclusion"]

    if evaluation["is_consensus"]:
        new_status = "consensus"
        final_conclusion = evaluation.get("consensus_summary") or f"Agreement reached: {evaluation['reasoning']}"
    elif evaluation["is_deadlock"] or new_deadlock_counter >= settings.deadlock_threshold:
        new_status = "deadlock"
        final_conclusion = f"Negotiation ended in deadlock after {state['current_turn'] + 1} turns. {evaluation['reasoning']}"

    # Update negotiation history
    new_history = list(state["negotiation_history"])
    new_history.append({"speaker": "Agent A", "message": state["agent_a_response"]})
    new_history.append({"speaker": "Agent B", "message": state["agent_b_response"]})

    return {
        "judge_evaluation": evaluation,
        "status": new_status,
        "final_conclusion": final_conclusion,
        "progress_score": evaluation["progress_score"],
        "deadlock_counter": new_deadlock_counter,
        "negotiation_history": new_history,
        "current_turn": state["current_turn"] + 1,
    }


# =============================================================================
# Workflow Execution
# =============================================================================


async def run_negotiation_turn(state: dict) -> dict:
    """
    Run a single turn of negotiation.

    Args:
        state: Current negotiation state

    Returns:
        Updated state after one turn
    """
    # Ensure state has all required fields
    full_state: NegotiationAgentState = {
        "goal": state.get("goal", ""),
        "agent_a_info": state.get("agent_a_info", ""),
        "agent_b_info": state.get("agent_b_info", ""),
        "negotiation_history": state.get("negotiation_history", []),
        "current_turn": state.get("current_turn", 0),
        "status": state.get("status", "in_progress"),
        "agent_a_response": state.get("agent_a_response", ""),
        "agent_b_response": state.get("agent_b_response", ""),
        "judge_evaluation": state.get("judge_evaluation", {}),
        "final_conclusion": state.get("final_conclusion"),
        "progress_score": state.get("progress_score", 0),
        "deadlock_counter": state.get("deadlock_counter", 0),
    }

    # Run Agent A
    agent_a_result = agent_a_node(full_state)
    full_state.update(agent_a_result)

    # Run Agent B
    agent_b_result = agent_b_node(full_state)
    full_state.update(agent_b_result)

    # Run Judge
    judge_result = judge_node(full_state)
    full_state.update(judge_result)

    return full_state


async def run_full_negotiation(
    goal: str,
    agent_a_info: str,
    agent_b_info: str,
) -> dict:
    """
    Run a complete negotiation until consensus or deadlock.

    Args:
        goal: The objective both agents must reach
        agent_a_info: Private information for Agent A
        agent_b_info: Private information for Agent B

    Returns:
        Final negotiation state
    """
    settings = get_settings()

    state: NegotiationAgentState = {
        "goal": goal,
        "agent_a_info": agent_a_info,
        "agent_b_info": agent_b_info,
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

    while state["status"] == "in_progress" and state["current_turn"] < settings.max_negotiation_turns:
        state = await run_negotiation_turn(state)

    # If max turns reached without resolution
    if state["status"] == "in_progress":
        state["status"] = "deadlock"
        state["final_conclusion"] = f"Negotiation ended after reaching maximum {settings.max_negotiation_turns} turns without agreement."

    return state
