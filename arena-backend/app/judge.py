"""Judge logic for evaluating negotiation progress."""
from __future__ import annotations
import json
import re
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from .config import get_settings
from .models import JudgeEvaluation


def get_llm() -> ChatAnthropic:
    """Get configured LLM instance."""
    settings = get_settings()
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        temperature=0.3,  # Lower temperature for more consistent judgments
    )


def format_history(history: list[dict]) -> str:
    """Format conversation history for the judge."""
    if not history:
        return "No conversation yet."

    formatted = []
    for entry in history:
        turn = entry.get("turn", "?")
        a_msg = entry.get("agent_a_message", "")
        b_msg = entry.get("agent_b_message", "")
        formatted.append(f"--- Turn {turn} ---")
        formatted.append(f"Alex (Partner A): {a_msg}")
        formatted.append(f"Jordan (Partner B): {b_msg}")

    return "\n".join(formatted)


async def evaluate_turn(
    goal: str,
    history: list[dict],
    agent_a_message: str,
    agent_b_message: str,
    turn_number: int
) -> JudgeEvaluation:
    """
    Evaluate a negotiation turn.
    The Judge sees ONLY public messages, never private information.
    """
    llm = get_llm()

    system_prompt = """You are an impartial Judge evaluating a negotiation between two partners (Alex and Jordan)
who are setting up a family trust fund.

IMPORTANT: You do NOT have access to either partner's private financial information or constraints.
You can only evaluate based on their public statements.

Your role:
1. Assess whether progress is being made toward agreement
2. Detect if the negotiation has stalled (deadlock)
3. Recognize when genuine consensus is reached
4. Provide brief, objective reasoning

CRITERIA FOR CONSENSUS:
- Both partners explicitly agree to specific terms
- Clear mutual acceptance (e.g., "I agree", "That works", "Deal", "Let's do that")
- Specific numbers or terms are mentioned and accepted by both

CRITERIA FOR DEADLOCK:
- Repeated positions without movement
- Explicit statements like "I can't go any further" from both sides
- Hostile or breakdown language
- No new proposals or compromises for multiple turns"""

    human_prompt = f"""NEGOTIATION GOAL: {goal}

CONVERSATION HISTORY:
{format_history(history)}

CURRENT TURN ({turn_number}):
Alex (Partner A): {agent_a_message}
Jordan (Partner B): {agent_b_message}

Evaluate this turn and respond with ONLY valid JSON (no markdown, no explanation):
{{
    "progress": true/false,
    "progress_score": <0-10, where 10 means deal reached>,
    "is_deadlock": true/false,
    "is_consensus": true/false,
    "reasoning": "<2-3 sentence explanation>",
    "consensus_summary": "<summary of agreed terms if consensus, otherwise null>"
}}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])

    try:
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        data = json.loads(content)

        return JudgeEvaluation(
            progress=data.get("progress", False),
            progress_score=max(0, min(10, data.get("progress_score", 0))),
            is_deadlock=data.get("is_deadlock", False),
            is_consensus=data.get("is_consensus", False),
            reasoning=data.get("reasoning", "Unable to parse judgment"),
            consensus_summary=data.get("consensus_summary")
        )
    except json.JSONDecodeError:
        # Default to cautious evaluation if parsing fails
        return JudgeEvaluation(
            progress=True,
            progress_score=5,
            is_deadlock=False,
            is_consensus=False,
            reasoning="Judge evaluation parsing failed - continuing negotiation",
            consensus_summary=None
        )
