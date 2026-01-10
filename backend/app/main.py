"""
Agent Negotiation API

A FastAPI application that provides a multi-agent negotiation system
using LangGraph and LangChain with Anthropic's Claude.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Manages startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    errors = settings.validate_config()

    if errors:
        print("\n" + "=" * 60)
        print("CONFIGURATION ERRORS")
        print("=" * 60)
        for error in errors:
            print(f"  - {error}")
        print("=" * 60)
        print("The API will start but negotiation features won't work.")
        print("Run GET /api/health to check status.\n")
    else:
        print("\n" + "=" * 60)
        print("AGENT NEGOTIATION API")
        print("=" * 60)
        print("Configuration OK. API ready.")
        print("=" * 60 + "\n")

    yield

    # Shutdown
    print("\nShutting down Agent Negotiation API...")


# Create FastAPI application
app = FastAPI(
    title="Agent Negotiation API",
    description="Multi-agent negotiation system using LangGraph and Claude",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative React port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Agent Negotiation API",
        "version": "1.0.0",
        "description": "Multi-agent negotiation system with Agent A, Agent B, and a Judge",
        "docs": "/docs",
        "health": "/api/health",
        "endpoints": {
            "start_negotiation": "POST /api/negotiate/start",
            "step_negotiation": "POST /api/negotiate/step",
            "run_full_negotiation": "POST /api/negotiate/run",
            "stream_negotiation": "POST /api/negotiate/stream",
            "get_status": "GET /api/negotiate/status/{session_id}",
        },
    }
