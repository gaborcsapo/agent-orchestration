"""
Agent Orchestration API

A FastAPI application that provides a multi-agent chat interface
using LangGraph, LangChain, and MongoDB Atlas.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.mongodb import MongoDB
from app.api.routes import router
from app.api.document_routes import router as document_router


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
        print("The API will start but some features may not work.")
        print("Run GET /api/health to check status.\n")
    else:
        # Connect to MongoDB
        try:
            await MongoDB.connect()
        except Exception as e:
            print(f"\nMongoDB connection failed: {e}")
            print("The API will start but database features won't work.\n")

    yield

    # Shutdown
    await MongoDB.disconnect()


# Create FastAPI application
app = FastAPI(
    title="Agent Orchestration API",
    description="Multi-agent chat API using LangGraph, LangChain, and MongoDB",
    version="0.1.0",
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
app.include_router(document_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Agent Orchestration API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }
