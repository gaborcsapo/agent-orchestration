"""Document ingestion API endpoints with streaming progress."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.context_agent import build_user_financial_context
from app.db.mongodb import MongoDB
from app.services.document_processor import (
    chunk_text,
    extract_image_text,
    extract_pdf_text,
)
from app.services.embeddings import embed_text, embed_texts, VoyageRateLimitError
from app.api.routes import router as chat_router  # if needed, but not part of this change

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# Response models
class IngestResponse(BaseModel):
    document_id: str
    user_id: str
    filename: str
    chunks_created: int
    status: str
    steps: list[dict]


class SearchResult(BaseModel):
    document_id: str
    filename: str
    content_preview: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str


class KeyFacts(BaseModel):
    income_indicators: list[str] = []
    debt_indicators: list[str] = []
    assets_mentioned: list[str] = []
    financial_goals: list[str] = []
    risk_factors: list[str] = []
    monthly_expenses: str = "unknown"


class ContextResponse(BaseModel):
    user_id: str
    roast: str
    financial_context: str
    key_facts: dict[str, Any]
    last_updated: Optional[str] = None
    document_count: int
    emoji: str = "🙂"  # Emoji representing financial profile
    negotiation_strategy: Optional[str] = None  # Secret instructions for the AI agent


class BuildContextResponse(BaseModel):
    user_id: str
    documents_processed: int
    context: dict[str, Any]


class UserProfileCreate(BaseModel):
    user_id: str
    age: int
    state: str
    filing_status: str = "single"  # single, married, head_of_household


class UserProfileResponse(BaseModel):
    user_id: str
    age: int
    state: str
    filing_status: str
    created_at: str


class NegotiationStrategyUpdate(BaseModel):
    strategy: str


# Helper functions
def get_documents_collection():
    return MongoDB.get_collection("documents")


def get_user_contexts_collection():
    return MongoDB.get_collection("user_contexts")


def get_user_profiles_collection():
    return MongoDB.get_collection("user_profiles")


def sse_message(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/documents/ingest-stream")
async def ingest_document_stream(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    """
    Ingest a document with streaming progress updates.
    Returns Server-Sent Events for each step.
    """

    async def generate_events() -> AsyncGenerator[str, None]:
        steps = []
        logger.info(f"Starting streaming ingestion for file: {file.filename}, user: {user_id}")

        # Step 1: File received
        step = {"step": 1, "name": "upload", "status": "completed", "message": f"File received: {file.filename}"}
        steps.append(step)
        yield sse_message("progress", step)

        # Validate file type
        content_type = file.content_type
        if content_type == "application/pdf":
            doc_type = "pdf"
        elif content_type in ["image/png", "image/jpeg", "image/webp", "image/gif"]:
            doc_type = "image"
        else:
            yield sse_message("error", {"message": f"Unsupported file type: {content_type}"})
            return

        # Read file
        file_bytes = await file.read()
        logger.info(f"File read complete, size: {len(file_bytes)} bytes")

        # Step 2: Extracting text
        from app.core.config import get_settings
        settings = get_settings()
        model_name = "PyMuPDF" if doc_type == "pdf" else f"Fireworks Vision ({settings.fireworks_vision_model.split('/')[-1]})"
        step = {
            "step": 2,
            "name": "extract",
            "status": "in_progress",
            "message": f"Extracting text using {model_name}...",
            "metadata": {
                "model": settings.fireworks_vision_model if doc_type == "image" else "PyMuPDF",
                "file_type": doc_type,
            }
        }
        steps.append(step)
        yield sse_message("progress", step)

        try:
            if doc_type == "pdf":
                content = extract_pdf_text(file_bytes)
            else:
                content = extract_image_text(file_bytes, content_type)

            # Show preview of extracted content
            preview = content[:200] + "..." if len(content) > 200 else content
            step = {
                "step": 2,
                "name": "extract",
                "status": "completed",
                "message": f"Extracted {len(content)} characters",
                "metadata": {
                    "characters": len(content),
                    "preview": preview,
                    "model": settings.fireworks_vision_model if doc_type == "image" else "PyMuPDF",
                }
            }
            steps[-1] = step
            logger.info(f"Extraction successful: {len(content)} characters")
            yield sse_message("progress", step)
        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}")
            yield sse_message("error", {"step": 2, "message": f"Failed to extract text: {str(e)}"})
            return

        if not content or not content.strip():
            yield sse_message("error", {"message": "Could not extract text from document"})
            return

        # Step 3: Chunking
        step = {"step": 3, "name": "chunk", "status": "in_progress", "message": "Chunking document..."}
        steps.append(step)
        yield sse_message("progress", step)

        chunks = chunk_text(content)
        step = {"step": 3, "name": "chunk", "status": "completed", "message": f"Created {len(chunks)} chunks"}
        steps[-1] = step
        logger.info(f"Chunking complete: {len(chunks)} chunks")
        yield sse_message("progress", step)

        # Step 4: Embedding with Voyage AI
        step = {
            "step": 4,
            "name": "embed",
            "status": "in_progress",
            "message": "Generating embeddings with Voyage AI...",
            "metadata": {
                "model": "voyage-finance-2",
                "chunks_to_embed": len(chunks),
            }
        }
        steps.append(step)
        yield sse_message("progress", step)

        try:
            embeddings = embed_texts(chunks)
            # Show sample embedding vector (first few dimensions)
            sample_embedding = embeddings[0][:10] if embeddings else []
            step = {
                "step": 4,
                "name": "embed",
                "status": "completed",
                "message": f"Generated {len(embeddings)} embeddings",
                "metadata": {
                    "model": "voyage-finance-2",
                    "embedding_count": len(embeddings),
                    "embedding_dimensions": len(embeddings[0]) if embeddings else 0,
                    "sample_vector": [round(x, 4) for x in sample_embedding],
                }
            }
            steps[-1] = step
            logger.info(f"Embeddings generated: {len(embeddings)}")
            yield sse_message("progress", step)
        except VoyageRateLimitError as e:
            logger.error(f"Voyage AI rate limit: {str(e)}")
            yield sse_message("error", {
                "step": 4,
                "message": str(e),
                "is_rate_limit": True
            })
            return
        except Exception as e:
            logger.error(f"Embedding failed: {str(e)}")
            yield sse_message("error", {"step": 4, "message": f"Failed to generate embeddings: {str(e)}"})
            return

        # Step 5: Storing in MongoDB
        step = {"step": 5, "name": "store", "status": "in_progress", "message": "Storing in MongoDB Atlas..."}
        steps.append(step)
        yield sse_message("progress", step)

        try:
            documents = get_documents_collection()
            doc = {
                "user_id": user_id,
                "filename": file.filename,
                "doc_type": doc_type,
                "content": content,
                "embedding": embeddings[0] if len(embeddings) == 1 else None,
                "metadata": {
                    "upload_date": datetime.utcnow(),
                    "content_type": content_type,
                    "file_size": len(file_bytes),
                },
                "chunks": [
                    {"text": chunk, "embedding": emb, "chunk_index": i}
                    for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
                ],
            }

            result = await documents.insert_one(doc)

            step = {"step": 5, "name": "store", "status": "completed", "message": f"Stored with ID: {str(result.inserted_id)[:8]}..."}
            steps[-1] = step
            logger.info(f"Document stored in MongoDB with ID: {result.inserted_id}")
            yield sse_message("progress", step)
        except Exception as e:
            logger.error(f"Storage failed: {str(e)}")
            yield sse_message("error", {"step": 5, "message": f"Failed to store in MongoDB: {str(e)}"})
            return

        # Final: Complete
        yield sse_message("complete", {
            "document_id": str(result.inserted_id),
            "user_id": user_id,
            "filename": file.filename,
            "chunks_created": len(chunks),
            "steps": steps,
        })

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    """
    Ingest a document (PDF or image) for a user.
    Non-streaming version for simple uploads.
    """
    steps = []

    # Validate file type
    content_type = file.content_type
    if content_type == "application/pdf":
        doc_type = "pdf"
    elif content_type in ["image/png", "image/jpeg", "image/webp", "image/gif"]:
        doc_type = "image"
    else:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type: {content_type}"
        )

    steps.append({"step": 1, "name": "upload", "status": "completed"})

    # Read file
    file_bytes = await file.read()

    # Extract text based on document type
    try:
        if doc_type == "pdf":
            content = extract_pdf_text(file_bytes)
        else:
            content = extract_image_text(file_bytes, content_type)
        steps.append({"step": 2, "name": "extract", "status": "completed"})
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to extract text: {str(e)}"
        )

    if not content or not content.strip():
        raise HTTPException(
            status_code=400, detail="Could not extract text from document"
        )

    # Chunk and embed
    chunks = chunk_text(content)
    steps.append({"step": 3, "name": "chunk", "status": "completed"})

    try:
        embeddings = embed_texts(chunks)
        steps.append({"step": 4, "name": "embed", "status": "completed"})
    except VoyageRateLimitError as e:
        raise HTTPException(
            status_code=429,  # 429 Too Many Requests
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate embeddings: {str(e)}"
        )

    # Store in MongoDB
    documents = get_documents_collection()
    doc = {
        "user_id": user_id,
        "filename": file.filename,
        "doc_type": doc_type,
        "content": content,
        "embedding": embeddings[0] if len(embeddings) == 1 else None,
        "metadata": {
            "upload_date": datetime.utcnow(),
            "content_type": content_type,
            "file_size": len(file_bytes),
        },
        "chunks": [
            {"text": chunk, "embedding": emb, "chunk_index": i}
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ],
    }

    result = await documents.insert_one(doc)
    steps.append({"step": 5, "name": "store", "status": "completed"})

    return IngestResponse(
        document_id=str(result.inserted_id),
        user_id=user_id,
        filename=file.filename or "unknown",
        chunks_created=len(chunks),
        status="ingested",
        steps=steps,
    )


@router.get("/documents/search", response_model=SearchResponse)
async def search_documents(
    user_id: str,
    query: str,
    limit: int = 5,
):
    """Vector search across user's documents."""
    try:
        query_embedding = embed_text(query)
    except VoyageRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to embed query: {str(e)}"
        )

    documents = get_documents_collection()

    pipeline = [
        {
            "$vectorSearch": {
                "index": "document_vector_index",
                "path": "chunks.embedding",
                "queryVector": query_embedding,
                "numCandidates": limit * 10,
                "limit": limit,
                "filter": {"user_id": user_id},
            }
        },
        {
            "$project": {
                "filename": 1,
                "content": 1,
                "score": {"$meta": "vectorSearchScore"},
                "user_id": 1,
            }
        },
    ]

    results = []
    try:
        async for doc in documents.aggregate(pipeline):
            results.append(
                SearchResult(
                    document_id=str(doc["_id"]),
                    filename=doc.get("filename", "unknown"),
                    content_preview=doc.get("content", "")[:500],
                    score=doc.get("score", 0.0),
                )
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Vector search failed. Ensure index is created in Atlas UI. Error: {str(e)}",
        )

    return SearchResponse(results=results, query=query)


@router.get("/documents", response_model=list[dict])
async def list_user_documents(user_id: str):
    """List all documents for a user."""
    documents = get_documents_collection()

    result = []
    async for doc in documents.find(
        {"user_id": user_id},
        {"content": 0, "chunks": 0, "embedding": 0},
    ):
        result.append(
            {
                "document_id": str(doc["_id"]),
                "filename": doc.get("filename"),
                "doc_type": doc.get("doc_type"),
                "upload_date": doc.get("metadata", {})
                .get("upload_date", "")
                .isoformat()
                if doc.get("metadata", {}).get("upload_date")
                else None,
            }
        )

    return result


@router.post("/users/{user_id}/build-context-stream")
async def build_context_stream(user_id: str):
    """Build/rebuild financial context with streaming progress updates."""

    async def generate_events() -> AsyncGenerator[str, None]:
        steps = []
        logger.info(f"Starting streaming context build for user: {user_id}")

        # Step 1: Fetching documents
        step = {"step": 1, "name": "fetch", "status": "in_progress", "message": "Fetching documents from MongoDB..."}
        steps.append(step)
        yield sse_message("progress", step)

        try:
            documents = get_documents_collection()
            user_docs = []
            async for doc in documents.find({"user_id": user_id}):
                user_docs.append(doc)

            if not user_docs:
                yield sse_message("error", {"message": f"No documents found for user: {user_id}"})
                return

            step = {
                "step": 1,
                "name": "fetch",
                "status": "completed",
                "message": f"Found {len(user_docs)} documents",
                "metadata": {"document_count": len(user_docs)}
            }
            steps[-1] = step
            yield sse_message("progress", step)
        except Exception as e:
            logger.error(f"Document fetch failed: {str(e)}")
            yield sse_message("error", {"step": 1, "message": f"Failed to fetch documents: {str(e)}"})
            return

        # Step 2: Analyzing with LLM
        from app.core.config import get_settings
        settings = get_settings()
        step = {
            "step": 2,
            "name": "analyze",
            "status": "in_progress",
            "message": "Analyzing financial documents with LLM...",
            "metadata": {
                "model": settings.fireworks_llm_model,
                "documents_to_analyze": len(user_docs)
            }
        }
        steps.append(step)
        yield sse_message("progress", step)

        try:
            context = await build_user_financial_context(user_id, user_docs)

            step = {
                "step": 2,
                "name": "analyze",
                "status": "completed",
                "message": "Financial analysis complete",
                "metadata": {
                    "model": settings.fireworks_llm_model,
                    "summary_length": len(context.get("summary", "")),
                    "risk_appetite": context.get("key_facts", {}).get("risk_appetite", "unknown"),
                }
            }
            steps[-1] = step
            yield sse_message("progress", step)
        except Exception as e:
            logger.error(f"Context analysis failed: {str(e)}")
            yield sse_message("error", {"step": 2, "message": f"Failed to analyze context: {str(e)}"})
            return

        # Step 3: Storing in MongoDB
        step = {"step": 3, "name": "store", "status": "in_progress", "message": "Storing context in MongoDB..."}
        steps.append(step)
        yield sse_message("progress", step)

        try:
            contexts = get_user_contexts_collection()
            await contexts.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "roast": context["roast"],
                        "financial_context": context["summary"],
                        "key_facts": context["key_facts"],
                        "emoji": context["emoji"],
                        "last_updated": datetime.utcnow(),
                        "document_ids": [str(doc["_id"]) for doc in user_docs],
                    }
                },
                upsert=True,
            )

            step = {"step": 3, "name": "store", "status": "completed", "message": "Context saved successfully"}
            steps[-1] = step
            yield sse_message("progress", step)
        except Exception as e:
            logger.error(f"Context storage failed: {str(e)}")
            yield sse_message("error", {"step": 3, "message": f"Failed to store context: {str(e)}"})
            return

        # Final: Complete
        yield sse_message("complete", {
            "user_id": user_id,
            "documents_processed": len(user_docs),
            "context": dict(context),
            "steps": steps,
        })

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/users/{user_id}/build-context", response_model=BuildContextResponse)
async def build_context(user_id: str):
    """Build/rebuild financial context for a user from their documents."""
    logger.info(f"Starting build_context for user: {user_id}")
    documents = get_documents_collection()
    user_docs = []
    async for doc in documents.find({"user_id": user_id}):
        user_docs.append(doc)

    if not user_docs:
        logger.warning(f"No documents found for user {user_id}")
        raise HTTPException(
            status_code=404, detail=f"No documents found for user: {user_id}"
        )

    logger.info(f"Found {len(user_docs)} documents. Calling context agent...")

    try:
        context = await build_user_financial_context(user_id, user_docs)
        logger.info("Context agent returned successfully")
    except Exception as e:
        logger.error(f"Context build failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to build context: {str(e)}"
        )

    contexts = get_user_contexts_collection()
    await contexts.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "roast": context["roast"],
                "financial_context": context["summary"],
                "key_facts": context["key_facts"],
                "emoji": context["emoji"],
                "last_updated": datetime.utcnow(),
                "document_ids": [str(doc["_id"]) for doc in user_docs],
            }
        },
        upsert=True,
    )
    logger.info(f"Context updated in MongoDB for user {user_id}")

    return BuildContextResponse(
        user_id=user_id,
        documents_processed=len(user_docs),
        context=dict(context),
    )


@router.get("/users/{user_id}/context", response_model=ContextResponse)
async def get_user_context(user_id: str):
    """Get financial context for a user."""
    contexts = get_user_contexts_collection()
    context = await contexts.find_one({"user_id": user_id})

    if not context:
        raise HTTPException(
            status_code=404,
            detail=f"No context found for user: {user_id}. Upload documents and build context first.",
        )

    return ContextResponse(
        user_id=user_id,
        roast=context.get("roast", "This portfolio is so mysterious, not even an AI can figure it out!"),
        financial_context=context.get("financial_context", ""),
        key_facts=context.get("key_facts", {}),
        last_updated=context.get("last_updated").isoformat()
        if context.get("last_updated")
        else None,
        document_count=len(context.get("document_ids", [])),
        emoji=context.get("emoji", "🙂"),
        negotiation_strategy=context.get("negotiation_strategy"),
    )


@router.post("/users/{user_id}/negotiation-strategy")
async def update_negotiation_strategy(
    user_id: str,
    update: NegotiationStrategyUpdate
):
    """Update the negotiation strategy for a user's AI agent."""
    contexts = get_user_contexts_collection()

    # Check if context exists
    context = await contexts.find_one({"user_id": user_id})
    if not context:
        raise HTTPException(
            status_code=404,
            detail=f"No context found for user: {user_id}. Build financial context first."
        )

    # Update the negotiation strategy
    await contexts.update_one(
        {"user_id": user_id},
        {"$set": {"negotiation_strategy": update.strategy}}
    )

    logger.info(f"Updated negotiation strategy for user {user_id}")

    return {
        "user_id": user_id,
        "negotiation_strategy": update.strategy,
        "message": "Negotiation strategy updated successfully"
    }


@router.post("/users/create", response_model=UserProfileResponse)
async def create_user_profile(profile: UserProfileCreate):
    """Create a new user profile with basic information."""
    profiles = get_user_profiles_collection()

    # Check if user already exists
    existing = await profiles.find_one({"user_id": profile.user_id})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"User {profile.user_id} already exists"
        )

    user_doc = {
        "user_id": profile.user_id,
        "age": profile.age,
        "state": profile.state,
        "filing_status": profile.filing_status,
        "created_at": datetime.utcnow(),
    }

    await profiles.insert_one(user_doc)
    logger.info(f"Created user profile for {profile.user_id}")

    return UserProfileResponse(
        user_id=profile.user_id,
        age=profile.age,
        state=profile.state,
        filing_status=profile.filing_status,
        created_at=user_doc["created_at"].isoformat(),
    )


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: str):
    """Get user profile information."""
    profiles = get_user_profiles_collection()
    profile = await profiles.find_one({"user_id": user_id})

    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"User profile not found: {user_id}. Create user first."
        )

    return UserProfileResponse(
        user_id=profile["user_id"],
        age=profile["age"],
        state=profile["state"],
        filing_status=profile["filing_status"],
        created_at=profile["created_at"].isoformat(),
    )
