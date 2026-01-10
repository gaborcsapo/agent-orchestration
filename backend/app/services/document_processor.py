"""Document processing: PDF extraction and image OCR via Fireworks AI."""
from __future__ import annotations

import base64
import json

import fitz  # PyMuPDF
import requests

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)



def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF."""
    logger.info(f"Extracting text from PDF, size: {len(pdf_bytes)} bytes")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    result = "\n\n".join(text_parts)
    logger.info(f"PDF extraction complete. Extracted {len(result)} characters.")
    return result


def extract_image_text(image_bytes: bytes, mime_type: str) -> str:
    """
    Extract text from image using Fireworks AI Vision model.

    Uses custom Llama 3.2 Vision deployment for OCR on financial documents.
    """
    logger.info(f"Extracting text from Image ({mime_type}), size: {len(image_bytes)} bytes")
    settings = get_settings()

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:{mime_type};base64,{b64_image}"

    url = "https://api.fireworks.ai/inference/v1/chat/completions"
    payload = {
        "model": settings.fireworks_vision_model,
        "max_tokens": 16384,
        "top_p": 1,
        "top_k": 40,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "temperature": 0.3,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract ALL text from this financial document image. "
                            "Include numbers, dates, account info, and any financial figures. "
                            "Format as plain text, preserving structure where possible."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.fireworks_api_key}"
    }

    logger.info("Calling Fireworks AI Vision model...")
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code != 200:
        logger.error(f"Fireworks API error: {response.status_code} - {response.text}")
        print(f"Fireworks API error: {response.status_code} - {response.text}")
        raise Exception(f"Fireworks API error: {response.status_code} - {response.text}")

    result = response.json()
    content = result["choices"][0]["message"]["content"]
    logger.info(f"Image OCR complete. Extracted {len(content)} characters.")
    return content


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """
    Simple text chunking for longer documents.

    Args:
        text: The text to chunk
        chunk_size: Maximum characters per chunk
        overlap: Character overlap between chunks

    Returns:
        List of text chunks
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
