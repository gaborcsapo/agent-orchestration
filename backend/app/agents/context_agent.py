"""Context Agent: Builds user financial profiles from documents using Fireworks AI."""
from __future__ import annotations

import json
import requests
from typing import Any, TypedDict

import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class FinancialContext(TypedDict):
    """Structured financial context for a user."""

    roast: str
    summary: str
    key_facts: dict[str, Any]
    emoji: str  # Emoji representing user's financial profile


SYSTEM_PROMPT = """You are a Financial Context Analyzer. Your job is to extract
key financial information from user documents and build a structured profile.

Output a JSON object with:
1. "roast": A single witty/sarcastic sentence roasting this portfolio (keep it fun and lighthearted, finance-themed)
2. "summary": A detailed 5-7 paragraph narrative summary of the user's financial situation, covering:
   - Overall financial health and current position
   - Income sources and stability
   - Asset composition and diversification
   - Debt situation and payment obligations
   - Spending patterns and lifestyle indicators
   - Long-term financial trajectory and potential concerns
   - Strengths and areas for improvement
3. "key_facts": An object containing:
   - "income_indicators": array of income sources/ranges mentioned with details
   - "monthly_income": REQUIRED - estimated monthly income after taxes as a string (e.g., "$5,000-$6,000"). If not in docs, estimate based on lifestyle/expenses, or use "$2,000-$4,000" as baseline
   - "total_assets": REQUIRED - estimated total assets as a string (e.g., "$50,000-$75,000"). If not in docs, estimate based on mentioned accounts/property, or use "$10,000-$25,000" as baseline
   - "monthly_liabilities": REQUIRED - estimated monthly debt payments/liabilities as a string (e.g., "$500-$1,000"). If not in docs, use "$0-$500" as baseline
   - "debt_indicators": array of debts/liabilities mentioned with specific amounts and types
   - "assets_mentioned": array of assets (accounts, property, investments) with specific values where available
   - "financial_goals": array of any goals/plans mentioned with timeframes
   - "risk_factors": array of any concerns or risks noted with detailed explanations
   - "monthly_expenses": estimated range if determinable with category breakdown
   - "risk_appetite": "conservative" | "moderate" | "aggressive" based on portfolio composition
   - "portfolio_allocation": object with "stocks_percent", "bonds_percent", "cash_percent", "other_percent" (estimate percentages)
   - "spending_patterns": detailed description of spending habits observed in documents (REQUIRED - if not explicit, infer from account balances, asset accumulation, lifestyle indicators)
   - "income_stability": assessment of income reliability (REQUIRED - e.g., "stable salary employment", "variable freelance income", "multiple income streams")
   - "emergency_fund_status": assessment of liquid savings adequacy (REQUIRED - e.g., "3-6 months expenses", "minimal buffer", "well-capitalized with 12+ months")
   - "debt_to_income_ratio": estimated ratio as string (REQUIRED - e.g., "25-30%", "under 20%", "minimal debt load")
   - "investment_strategy": description of apparent investment approach and philosophy (REQUIRED - infer from portfolio composition, account types, asset allocation)
   - "retirement_readiness": assessment of retirement savings progress based on age (REQUIRED - evaluate retirement accounts relative to age and income)
   - "insurance_coverage": any insurance policies mentioned or inferred needs (REQUIRED - if not mentioned, note "not evident in documents, recommend review")
   - "tax_situation": observations about tax efficiency and potential concerns (REQUIRED - infer from account types like 401k, IRA, taxable accounts, HSA)
   - "financial_sophistication": assessment of financial knowledge level (REQUIRED - infer from investment choices, account types, diversification, language used)

IMPORTANT RULES:
- ALL fields marked REQUIRED must have substantive values (never "unknown", "not specified", or empty strings)
- Make intelligent inferences and educated guesses based on available context clues
- For monthly_income, total_assets, and monthly_liabilities: use baseline ranges if no data (as specified above)
- For the 9 new detailed fields: analyze the documents and infer reasonable assessments
- Examples of good inferences:
  * If portfolio shows tech stocks and crypto → "aggressive risk appetite, growth-focused investor"
  * If documents show 401k and IRA accounts → "tax-advantaged retirement strategy, moderate tax planning"
  * If young person with high savings rate → "disciplined saver, above-average financial maturity"
  * If only checking account visible → "limited investment sophistication, may benefit from diversification guidance"
  * If high assets but low mentioned income → "possibly high net worth individual or inherited wealth"
- Be thorough and detailed - extract as much information as possible
- For arrays, provide rich detail, not just bullet points
- The summary should be comprehensive and insightful (aim for 800-1200 words)
- Output ONLY valid JSON, no additional text before or after."""


def select_emoji_from_roast(roast: str) -> str:
    """
    Select an appropriate emoji based on the roast sentiment.

    Returns an emoji character representing the user's financial profile.
    Only uses people, animals, or face emojis (no objects/symbols).
    """
    roast_lower = roast.lower()

    # Wealthy/Success indicators - People/Animals
    if any(word in roast_lower for word in ["rich", "wealth", "millionaire", "loaded", "fortune", "jackpot", "crushing", "winning", "champion"]):
        return "🤑"  # Money-face (wealthy)
    if any(word in roast_lower for word in ["beast", "legend", "king", "queen", "boss"]):
        return "👑"  # Crown person
    if any(word in roast_lower for word in ["rocket", "moon", "soaring", "skyrocket", "surge", "fire", "hot", "blazing"]):
        return "🦅"  # Eagle (soaring high)

    # Conservative/Safe indicators - Slow/Cautious animals
    if any(word in roast_lower for word in ["safe", "cautious", "conservative", "careful"]):
        return "🐌"  # Snail (slow and steady)
    if any(word in roast_lower for word in ["boring", "sleep", "snooze", "yawn", "dull"]):
        return "😴"  # Sleeping face
    if any(word in roast_lower for word in ["turtle", "slow", "crawl", "gradual"]):
        return "🐢"  # Turtle
    if any(word in roast_lower for word in ["owl", "wise", "patient"]):
        return "🦉"  # Owl (wise)

    # Risky/Aggressive indicators - Wild animals/faces
    if any(word in roast_lower for word in ["risky", "gamble", "casino", "bet", "dice", "yolo", "wild"]):
        return "🐵"  # Monkey (playful/risky)
    if any(word in roast_lower for word in ["crazy", "insane", "mad"]):
        return "🤪"  # Crazy face
    if any(word in roast_lower for word in ["shark", "aggressive", "predator", "hunter"]):
        return "🦈"  # Shark
    if any(word in roast_lower for word in ["bull", "bullish", "strong"]):
        return "🐂"  # Bull

    # Struggling/Negative indicators - Sad faces/animals
    if any(word in roast_lower for word in ["broke", "poor", "empty", "zero", "nothing"]):
        return "😭"  # Crying loudly
    if any(word in roast_lower for word in ["crying", "tears", "sad", "depressed"]):
        return "😢"  # Crying face
    if any(word in roast_lower for word in ["crash", "sink", "fall", "plunge", "drop"]):
        return "😱"  # Shocked/scared face
    if any(word in roast_lower for word in ["storm", "disaster", "crisis"]):
        return "😰"  # Anxious face with sweat

    # Confused/Unclear indicators
    if any(word in roast_lower for word in ["confused", "lost", "mystery", "puzzle", "unclear"]):
        return "🤔"  # Thinking face
    if any(word in roast_lower for word in ["maze", "labyrinth", "tangled"]):
        return "😵"  # Dizzy face
    if any(word in roast_lower for word in ["strange", "weird", "unusual"]):
        return "😬"  # Grimacing face

    # Balanced/Moderate indicators - Neutral animals/faces
    if any(word in roast_lower for word in ["balanced", "equilibrium", "moderate"]):
        return "🙂"  # Slightly smiling face
    if any(word in roast_lower for word in ["growing", "progress", "improving"]):
        return "😊"  # Smiling face
    if any(word in roast_lower for word in ["steady", "stable", "solid"]):
        return "😌"  # Relieved face
    if any(word in roast_lower for word in ["cat", "independent", "comfortable"]):
        return "🐱"  # Cat face

    # Strategic/Smart indicators - Smart animals
    if any(word in roast_lower for word in ["fox", "clever", "cunning", "strategic"]):
        return "🦊"  # Fox (clever)
    if any(word in roast_lower for word in ["smart", "intelligent", "genius", "brain"]):
        return "🤓"  # Nerd face (smart)
    if any(word in roast_lower for word in ["detective", "investigate"]):
        return "🕵️"  # Detective

    # Default: neutral smiley
    return "😊"


async def build_user_financial_context(
    user_id: str,
    documents: list[dict[str, Any]],
) -> FinancialContext:
    """
    Analyze user documents and build a financial context profile.

    Uses Fireworks AI for fast inference with Llama 3.1 70B model.

    This context will be used by Part 2 (agent negotiation) to understand
    the user's financial situation.

    Args:
        user_id: The user identifier
        documents: List of document dicts with 'filename' and 'content' keys

    Returns:
        FinancialContext with summary and key_facts
    """
    logger.info(f"Building financial context for user {user_id} from {len(documents)} documents")
    print(f"[context_agent] Building financial context for user {user_id} from {len(documents)} documents")
    settings = get_settings()

    # Combine document contents (truncate if too long)
    all_content = "\n\n---DOCUMENT---\n\n".join(
        [f"[{doc['filename']}]\n{doc['content'][:3000]}" for doc in documents]
    )

    # Truncate total to ~30k chars
    if len(all_content) > 30000:
        logger.warning(f"Combined content length {len(all_content)} exceeds limit. Truncating to 30000 chars.")
        all_content = all_content[:30000] + "\n...[truncated]"
    else:
        logger.info(f"Combined content length: {len(all_content)} chars")

    # Call Fireworks AI directly
    url = "https://api.fireworks.ai/inference/v1/chat/completions"
    payload = {
        "model": settings.fireworks_llm_model,
        "max_tokens": 8192,  # Increased for longer, more detailed output
        "temperature": 0.3,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"Analyze these financial documents for user {user_id}:\n\n{all_content}"
            }
        ]
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.fireworks_api_key}"
    }

    logger.info(f"Sending request to Fireworks LLM: {settings.fireworks_llm_model}")
    print(f"[context_agent] Calling Fireworks API with model: {settings.fireworks_llm_model}")

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        print(f"[context_agent] Fireworks API response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Fireworks API error: {response.status_code} - {response.text}")
            print(f"[context_agent] ERROR: {response.status_code} - {response.text}")
            raise Exception(f"Fireworks API error: {response.status_code} - {response.text}")

        result = response.json()
        content = result["choices"][0]["message"]["content"]
        logger.info(f"Received response from LLM, length: {len(content)} chars")
        print(f"[context_agent] Received LLM response, length: {len(content)} chars")
    except Exception as e:
        logger.error(f"Failed to call Fireworks API: {str(e)}")
        print(f"[context_agent] EXCEPTION: {str(e)}")
        raise

    # Parse response - try to extract JSON
    parsed_data = None
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            parsed_data = json.loads(content[start:end])
            logger.info("Successfully parsed JSON context from LLM response")
            print("[context_agent] Successfully parsed JSON from LLM response")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from LLM response: {str(e)}")
        print(f"[context_agent] JSON parse error: {str(e)}")

    # Select emoji based on roast
    if parsed_data:
        roast_text = parsed_data.get("roast", "This portfolio is so mysterious, even Sherlock Holmes couldn't deduce its strategy.")
        emoji = select_emoji_from_roast(roast_text)

        return FinancialContext(
            roast=roast_text,
            summary=parsed_data.get("summary", content),
            key_facts=parsed_data.get("key_facts", {}),
            emoji=emoji,
        )

    # Fallback: return raw response as summary with baseline estimates
    print("[context_agent] Using fallback - returning raw response as summary")
    fallback_roast = "This portfolio is playing hard to get - no clear strategy detected!"
    return FinancialContext(
        roast=fallback_roast,
        summary=content,
        key_facts={
            "income_indicators": [],
            "monthly_income": "$2,000-$4,000",  # Baseline estimate
            "total_assets": "$10,000-$25,000",  # Baseline estimate
            "monthly_liabilities": "$0-$500",  # Baseline estimate
            "debt_indicators": [],
            "assets_mentioned": [],
            "financial_goals": [],
            "risk_factors": ["Could not parse structured data from documents - JSON parsing failed"],
            "monthly_expenses": "$1,500-$3,000",
            "risk_appetite": "moderate",
            "portfolio_allocation": {
                "stocks_percent": "insufficient data",
                "bonds_percent": "insufficient data",
                "cash_percent": "insufficient data",
                "other_percent": "insufficient data",
            },
            "spending_patterns": "Unable to determine spending patterns from provided documents. Recommend tracking expenses for 2-3 months.",
            "income_stability": "Stability assessment requires more detailed income documentation",
            "emergency_fund_status": "Not evident in documents - liquid savings status unclear",
            "debt_to_income_ratio": "Unable to calculate - requires comprehensive income and debt information",
            "investment_strategy": "Investment approach not clearly evident from documents provided. May indicate early-stage investor or limited portfolio.",
            "retirement_readiness": "Retirement planning status unclear - recommend age-based assessment with financial advisor",
            "insurance_coverage": "No insurance policies evident in documents. Recommend comprehensive insurance review.",
            "tax_situation": "Tax efficiency assessment requires additional detail on account types and income sources",
            "financial_sophistication": "Financial literacy level unclear from documents - may benefit from financial education resources",
        },
        emoji=select_emoji_from_roast(fallback_roast),
    )
