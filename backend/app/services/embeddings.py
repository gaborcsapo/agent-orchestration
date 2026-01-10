"""Voyage AI embedding service for document vectors."""
from __future__ import annotations

import logging
import voyageai

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class VoyageRateLimitError(Exception):
    """Custom exception for Voyage AI rate limiting."""
    pass


def get_voyage_client() -> voyageai.Client:
    """Get Voyage AI client instance."""
    settings = get_settings()
    return voyageai.Client(api_key=settings.voyage_api_key)


def embed_text(text: str) -> list[float]:
    """Generate embedding for a single text using Voyage AI."""
    client = get_voyage_client()
    try:
        # Use voyage-finance-2 for financial documents
        result = client.embed([text], model="voyage-finance-2")
        return result.embeddings[0]
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Voyage AI embedding error: {error_msg}")

        # Check for rate limiting
        if "rate limit" in error_msg.lower() or "payment method" in error_msg.lower():
            raise VoyageRateLimitError(
                "Voyage AI rate limit exceeded. Please add a payment method at "
                "https://dashboard.voyageai.com/ to increase your rate limits. "
                "Free tier: 3 requests/min, 10K tokens/min."
            )
        raise


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts."""
    if not texts:
        return []

    client = get_voyage_client()
    try:
        result = client.embed(texts, model="voyage-finance-2")
        return result.embeddings
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Voyage AI batch embedding error: {error_msg}")
        print(f"[embeddings] Voyage AI error: {error_msg}")

        # Check for rate limiting
        if "rate limit" in error_msg.lower() or "payment method" in error_msg.lower():
            raise VoyageRateLimitError(
                "Voyage AI rate limit exceeded. Please add a payment method at "
                "https://dashboard.voyageai.com/ to increase your rate limits. "
                "Free tier: 3 requests/min, 10K tokens/min. Wait a minute and try again."
            )
        raise
