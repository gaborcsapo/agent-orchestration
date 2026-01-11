"""MongoDB connection for Arena Backend."""
from __future__ import annotations
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from .config import get_settings

# Global database client
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None
_connected: bool = False


async def connect_db() -> AsyncIOMotorDatabase:
    """Connect to MongoDB and return database instance."""
    global _client, _db, _connected
    settings = get_settings()

    if _client is None:
        _client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        _db = _client[settings.mongodb_db_name]

        # Test connection (but don't fail if it times out)
        try:
            await _client.admin.command('ping')
            print(f"[Arena] Connected to MongoDB: {settings.mongodb_db_name}")
            _connected = True
        except Exception as e:
            print(f"[Arena] MongoDB connection warning: {e}")
            print(f"[Arena] Will retry on first database operation")
            _connected = False

    return _db


async def close_db():
    """Close MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        print("MongoDB connection closed")


def get_db() -> AsyncIOMotorDatabase:
    """Get database instance (must be connected first)."""
    if _db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _db
