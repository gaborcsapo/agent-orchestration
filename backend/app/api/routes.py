"""
API Routes for the Agent Orchestration application.

Endpoints:
- POST /api/chat: Send a message and get an agent response
- GET /api/conversations: List all conversations
- GET /api/conversations/{id}: Get conversation details
- DELETE /api/conversations/{id}: Delete a conversation
- GET /api/health: Health check endpoint
"""

from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from app.db.models import (
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    ConversationDetailResponse,
    Conversation,
    Message,
    HealthResponse,
)
from app.db.mongodb import get_conversations_collection, get_messages_collection
from app.agents import run_agent_workflow
from app.core.config import get_settings

router = APIRouter(prefix="/api")


# =============================================================================
# Chat Endpoints
# =============================================================================


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message through the multi-agent workflow.

    If conversation_id is provided, continues existing conversation.
    Otherwise, creates a new conversation.
    """
    conversations = get_conversations_collection()
    messages = get_messages_collection()

    # Get or create conversation
    if request.conversation_id:
        conversation_id = request.conversation_id
        # Verify conversation exists
        conv = await conversations.find_one({"_id": ObjectId(conversation_id)})
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # Create new conversation
        conv_doc = {
            "title": request.message[:50] + "..." if len(request.message) > 50 else request.message,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = await conversations.insert_one(conv_doc)
        conversation_id = str(result.inserted_id)

    # Save user message
    user_message = {
        "conversation_id": conversation_id,
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow(),
    }
    await messages.insert_one(user_message)

    # Get conversation history for context
    history_cursor = messages.find({"conversation_id": conversation_id}).sort(
        "timestamp", 1
    )
    history = []
    async for msg in history_cursor:
        history.append({"role": msg["role"], "content": msg["content"]})

    # Run the agent workflow
    try:
        result = await run_agent_workflow(request.message, history[:-1])  # Exclude current message
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Agent workflow failed: {str(e)}"
        )

    # Save assistant message
    assistant_message = {
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": result["response"],
        "agent_steps": result["agent_steps"],
        "timestamp": datetime.utcnow(),
    }
    await messages.insert_one(assistant_message)

    # Update conversation timestamp
    await conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"updated_at": datetime.utcnow()}},
    )

    return ChatResponse(
        conversation_id=conversation_id,
        response=result["response"],
        agent_steps=result["agent_steps"],
    )


# =============================================================================
# Conversation Endpoints
# =============================================================================


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations():
    """List all conversations, most recent first."""
    conversations = get_conversations_collection()

    conv_list = []
    async for conv in conversations.find().sort("updated_at", -1):
        conv_list.append(
            Conversation(
                id=str(conv["_id"]),
                title=conv.get("title", "Untitled"),
                created_at=conv.get("created_at", datetime.utcnow()),
                updated_at=conv.get("updated_at", datetime.utcnow()),
            )
        )

    return ConversationListResponse(conversations=conv_list)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str):
    """Get conversation details with all messages."""
    conversations = get_conversations_collection()
    messages_coll = get_messages_collection()

    try:
        conv = await conversations.find_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    msg_list = []
    async for msg in messages_coll.find({"conversation_id": conversation_id}).sort(
        "timestamp", 1
    ):
        msg_list.append(
            Message(
                id=str(msg["_id"]),
                conversation_id=conversation_id,
                role=msg["role"],
                content=msg["content"],
                agent=msg.get("agent"),
                timestamp=msg.get("timestamp", datetime.utcnow()),
            )
        )

    return ConversationDetailResponse(
        conversation=Conversation(
            id=str(conv["_id"]),
            title=conv.get("title", "Untitled"),
            created_at=conv.get("created_at", datetime.utcnow()),
            updated_at=conv.get("updated_at", datetime.utcnow()),
        ),
        messages=msg_list,
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages."""
    conversations = get_conversations_collection()
    messages = get_messages_collection()

    try:
        result = await conversations.delete_one({"_id": ObjectId(conversation_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete associated messages
    await messages.delete_many({"conversation_id": conversation_id})

    return {"status": "deleted", "conversation_id": conversation_id}


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check the health of all services.

    Returns status of:
    - MongoDB connection
    - Anthropic API configuration
    - Any configuration errors
    """
    settings = get_settings()
    errors = settings.validate_config()

    # Check MongoDB
    mongodb_status = "not_configured"
    if settings.mongodb_uri and "username:password" not in settings.mongodb_uri:
        try:
            from app.db.mongodb import MongoDB
            if MongoDB.client:
                await MongoDB.client.admin.command("ping")
                mongodb_status = "connected"
            else:
                mongodb_status = "not_connected"
        except Exception as e:
            mongodb_status = f"error: {str(e)}"

    # Check Anthropic
    anthropic_status = "not_configured"
    if settings.anthropic_api_key and settings.anthropic_api_key != "your-anthropic-api-key-here":
        anthropic_status = "configured"

    overall_status = "healthy" if not errors else "unhealthy"

    return HealthResponse(
        status=overall_status,
        mongodb=mongodb_status,
        anthropic=anthropic_status,
        errors=errors,
    )
