"""Agent logic for thinking generation, BATNA analysis, and CI Gateway filtering."""
from __future__ import annotations
import json
import re
from typing import Optional
from datetime import datetime
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from .config import get_settings
from .models import (
    BATNAAnalysis,
    CIGatewayDecision,
    CIGatewayLog,
    AuditEntry,
)


def get_llm() -> ChatAnthropic:
    """Get configured LLM instance."""
    settings = get_settings()
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        temperature=0.7,
    )


def format_history(history: list[dict]) -> str:
    """Format conversation history for prompts."""
    if not history:
        return "No conversation yet - this is the opening turn."

    formatted = []
    for entry in history:
        agent = entry.get("agent", "Unknown")
        message = entry.get("message", "")
        formatted.append(f"[{agent}]: {message}")

    return "\n".join(formatted)


async def extract_batna(private_info: str, goal: str) -> BATNAAnalysis:
    """Extract BATNA from private information using LLM."""
    llm = get_llm()

    prompt = f"""Analyze this negotiation context and extract the BATNA (Best Alternative to Negotiated Agreement).

NEGOTIATION GOAL: {goal}

PRIVATE INFORMATION:
{private_info}

Your task:
1. Identify the walk-away point or best alternative if no deal is reached
2. If there's a specific monetary value, extract it
3. Explain the reasoning

Respond with ONLY valid JSON (no markdown):
{{
    "batna_value": <number or null if not applicable>,
    "batna_description": "<description of the walk-away point>",
    "reasoning": "<why this is the BATNA>"
}}"""

    response = llm.invoke([HumanMessage(content=prompt)])

    try:
        # Try to parse JSON from response
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        data = json.loads(content)
        return BATNAAnalysis(
            batna_value=data.get("batna_value"),
            batna_description=data.get("batna_description", "Unknown"),
            current_offer_acceptable=True,  # Will be evaluated later
            reasoning=data.get("reasoning", "")
        )
    except (json.JSONDecodeError, KeyError):
        return BATNAAnalysis(
            batna_value=None,
            batna_description="Could not extract specific BATNA",
            current_offer_acceptable=True,
            reasoning="BATNA extraction failed, proceeding with caution"
        )


async def generate_thinking(
    private_info: str,
    goal: str,
    history: list[dict],
    turn_number: int,
    agent_id: str,
    batna: BATNAAnalysis
) -> dict:
    """Generate agent's internal reasoning (never shared with opponent)."""
    llm = get_llm()

    agent_role = "Partner A" if agent_id == "A" else "Partner B"

    system_prompt = f"""You are {agent_role} in a negotiation between two partners about setting up a trust fund.

NEGOTIATION GOAL: {goal}

YOUR PRIVATE INFORMATION (ONLY YOU KNOW THIS - NEVER REVEAL DIRECTLY):
{private_info}

YOUR BATNA (Walk-away Point):
{batna.batna_description}
{f"Minimum acceptable value: ${batna.batna_value:,.0f}" if batna.batna_value else ""}

You are a strategic but fair negotiator. Think through your approach carefully."""

    human_prompt = f"""CONVERSATION SO FAR:
{format_history(history)}

This is turn {turn_number}. Think step-by-step through your strategy:

1. What has the conversation revealed about my partner's position?
2. What are my constraints based on my private information?
3. How does the current state compare to my BATNA?
4. What strategy should I use this turn?
5. What key points should I make (without revealing sensitive details)?

Respond with ONLY valid JSON (no markdown):
{{
    "steps": [
        "Step 1 analysis...",
        "Step 2 analysis...",
        "Step 3 analysis...",
        "Step 4 analysis...",
        "Step 5 analysis..."
    ],
    "strategy": "<name of strategy: e.g., 'Anchoring', 'Compromise', 'Value Creation'>",
    "key_insight": "<most important takeaway for this turn>",
    "proposed_approach": "<what you plan to say/propose>"
}}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "steps": ["Analyzing the situation...", "Considering my constraints...", "Planning response..."],
            "strategy": "Adaptive",
            "key_insight": "Need to balance my interests with finding common ground",
            "proposed_approach": "Continue negotiating constructively"
        }


async def generate_public_response(
    thinking: dict,
    goal: str,
    history: list[dict],
    private_info: str,
    agent_id: str,
    turn_number: int
) -> str:
    """Generate the public response based on thinking."""
    llm = get_llm()

    agent_role = "Partner A" if agent_id == "A" else "Partner B"

    system_prompt = f"""You are {agent_role} negotiating a trust fund setup with your partner.

GOAL: {goal}

Your strategy for this turn: {thinking.get('strategy', 'Collaborative')}
Your key insight: {thinking.get('key_insight', '')}
Your planned approach: {thinking.get('proposed_approach', '')}

CRITICAL RULES:
1. NEVER mention your exact walk-away point or minimum acceptable amount
2. NEVER reveal your private financial constraints directly
3. Be strategic but maintain a collaborative, partner-like tone
4. Focus on shared interests and family goals
5. Make concrete proposals when appropriate
6. Keep response concise (2-4 sentences)"""

    human_prompt = f"""CONVERSATION SO FAR:
{format_history(history)}

This is turn {turn_number}. Generate your public response.
Remember: You're negotiating with your partner, not an adversary. Be firm but fair.

Respond with ONLY the message you want to say (no JSON, no formatting):"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])

    return response.content.strip()


async def apply_ci_gateway(
    raw_response: str,
    private_info: str,
    batna: BATNAAnalysis,
    agent_id: str
) -> CIGatewayLog:
    """Apply Contextual Integrity Gateway to filter sensitive information."""
    llm = get_llm()

    prompt = f"""You are a Contextual Integrity Gateway. Your job is to review a negotiation message
and ensure no sensitive private information leaks.

PROPOSED MESSAGE:
"{raw_response}"

SENSITIVE INFORMATION THAT MUST NOT BE REVEALED:
{private_info}

BATNA (Walk-away point - NEVER reveal):
{batna.batna_description}
{f"Value: ${batna.batna_value:,.0f}" if batna.batna_value else ""}

Check for these violations:
1. DIRECT MENTION of exact walk-away price, minimum, or BATNA value
2. DESPERATION SIGNALS (urgent deadlines, financial stress, "need this to work")
3. EXACT FINANCIAL FIGURES from private constraints
4. LEVERAGE-DESTROYING INFORMATION (things that weaken negotiating position)

For each issue found:
- BLOCK: Remove completely if it's a deal-breaker leak
- TRANSFORM: Rephrase to be less specific (e.g., "limited budget" instead of "$50,000 max")
- ALLOW: Safe to include

Respond with ONLY valid JSON (no markdown):
{{
    "decisions": [
        {{
            "original": "<problematic phrase>",
            "action": "ALLOW|BLOCK|TRANSFORM",
            "result": "<transformed version if TRANSFORM, null if BLOCK/ALLOW>",
            "reason": "<why this decision>"
        }}
    ],
    "filtered_message": "<the safe final message>"
}}

If the message is already safe, return:
{{
    "decisions": [{{"original": "entire message", "action": "ALLOW", "result": null, "reason": "No sensitive information detected"}}],
    "filtered_message": "{raw_response}"
}}"""

    response = llm.invoke([HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        data = json.loads(content)

        decisions = [
            CIGatewayDecision(
                original=d.get("original", ""),
                action=d.get("action", "ALLOW"),
                result=d.get("result"),
                reason=d.get("reason", "")
            )
            for d in data.get("decisions", [])
        ]

        return CIGatewayLog(
            decisions=decisions,
            original_message=raw_response,
            filtered_message=data.get("filtered_message", raw_response)
        )
    except json.JSONDecodeError:
        # If parsing fails, pass through the original (safe default)
        return CIGatewayLog(
            decisions=[CIGatewayDecision(
                original="entire message",
                action="ALLOW",
                result=None,
                reason="CI Gateway parsing failed - defaulting to allow"
            )],
            original_message=raw_response,
            filtered_message=raw_response
        )


async def validate_against_batna(
    response: str,
    history: list[dict],
    batna: BATNAAnalysis
) -> tuple[bool, Optional[str]]:
    """
    Validate that any acceptance in the response doesn't violate BATNA.
    Returns (is_valid, rejection_reason).
    """
    if batna.batna_value is None:
        # No numerical BATNA, can't auto-validate
        return True, None

    llm = get_llm()

    prompt = f"""Analyze this negotiation message to determine if it accepts a specific deal.

MESSAGE:
"{response}"

RECENT CONVERSATION:
{format_history(history[-4:] if len(history) > 4 else history)}

Questions:
1. Does this message explicitly ACCEPT a specific monetary amount or deal?
2. If yes, what is the accepted value?

Respond with ONLY valid JSON:
{{
    "accepts_deal": true/false,
    "accepted_value": <number or null>,
    "reasoning": "<brief explanation>"
}}"""

    result = llm.invoke([HumanMessage(content=prompt)])

    try:
        content = result.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        data = json.loads(content)

        if data.get("accepts_deal") and data.get("accepted_value"):
            accepted_value = float(data["accepted_value"])
            if accepted_value < batna.batna_value:
                return False, f"Cannot accept ${accepted_value:,.0f} - below BATNA of ${batna.batna_value:,.0f}"

        return True, None
    except (json.JSONDecodeError, ValueError, TypeError):
        return True, None


async def process_turn(
    session_id: str,
    goal: str,
    history: list[dict],
    turn_number: int,
    private_info: str,
    agent_id: str,
    db
) -> tuple[str, AuditEntry]:
    """
    Process a complete turn for an agent.
    Returns (public_message, audit_entry).
    """
    settings = get_settings()

    # 1. Extract BATNA from private info
    batna = await extract_batna(private_info, goal)

    # 2. Generate thinking steps
    thinking = await generate_thinking(
        private_info=private_info,
        goal=goal,
        history=history,
        turn_number=turn_number,
        agent_id=agent_id,
        batna=batna
    )

    # 3. Generate public response
    raw_response = await generate_public_response(
        thinking=thinking,
        goal=goal,
        history=history,
        private_info=private_info,
        agent_id=agent_id,
        turn_number=turn_number
    )

    # 4. Apply CI Gateway filter
    ci_log = await apply_ci_gateway(
        raw_response=raw_response,
        private_info=private_info,
        batna=batna,
        agent_id=agent_id
    )

    # 5. Validate against BATNA
    is_valid, rejection_reason = await validate_against_batna(
        response=ci_log.filtered_message,
        history=history,
        batna=batna
    )

    # If BATNA validation fails, regenerate with rejection
    final_message = ci_log.filtered_message
    if not is_valid:
        # Override message with BATNA-respecting rejection
        final_message = f"I appreciate the offer, but I need to think about whether that works for our family's goals. {thinking.get('proposed_approach', 'Can we explore other options?')}"
        ci_log.decisions.append(CIGatewayDecision(
            original=ci_log.filtered_message,
            action="BLOCK",
            result=final_message,
            reason=f"BATNA VALIDATION: {rejection_reason}"
        ))
        ci_log.filtered_message = final_message

    # Update BATNA analysis with validation result
    batna.current_offer_acceptable = is_valid

    # 6. Create audit entry
    audit_entry = AuditEntry(
        turn=turn_number,
        timestamp=datetime.utcnow(),
        thinking_steps=thinking.get("steps", []),
        strategy=thinking.get("strategy", "Unknown"),
        batna_analysis=batna,
        ci_gateway_log=ci_log,
        final_message=final_message
    )

    # 7. Write to MongoDB audit trail (optional - don't fail if unavailable)
    try:
        await db[settings.audit_collection].insert_one({
            "session_id": session_id,
            "turn": turn_number,
            "timestamp": audit_entry.timestamp,
            "thinking_steps": audit_entry.thinking_steps,
            "strategy": audit_entry.strategy,
            "batna_analysis": {
                "batna_value": batna.batna_value,
                "batna_description": batna.batna_description,
                "current_offer_acceptable": batna.current_offer_acceptable,
                "reasoning": batna.reasoning
            },
            "ci_gateway_log": {
                "original_message": ci_log.original_message,
                "filtered_message": ci_log.filtered_message,
                "decisions": [
                    {
                        "original": d.original,
                        "action": d.action,
                        "result": d.result,
                        "reason": d.reason
                    }
                    for d in ci_log.decisions
                ]
            },
            "final_message": final_message
        })
    except Exception as e:
        print(f"[Agent {agent_id}] MongoDB audit write skipped: {e}")

    return final_message, audit_entry
