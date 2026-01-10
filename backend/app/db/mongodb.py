"""
MongoDB connection management using Motor (async driver).
Provides database and collection access with connection pooling.
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import get_settings


class MongoDB:
    """MongoDB connection manager."""

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    @classmethod
    async def connect(cls) -> None:
        """Establish connection to MongoDB."""
        settings = get_settings()

        if not settings.mongodb_uri:
            raise ValueError(
                "MongoDB URI not configured. "
                "Please set MONGODB_URI in your .env file."
            )

        cls.client = AsyncIOMotorClient(settings.mongodb_uri)
        cls.db = cls.client[settings.mongodb_db_name]

        # Verify connection
        try:
            await cls.client.admin.command("ping")
            print(f"Connected to MongoDB database: {settings.mongodb_db_name}")
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to MongoDB: {e}\n"
                "Please verify your MONGODB_URI is correct."
            )

    @classmethod
    async def disconnect(cls) -> None:
        """Close MongoDB connection."""
        if cls.client:
            cls.client.close()
            print("Disconnected from MongoDB")

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if cls.db is None:
            raise RuntimeError(
                "Database not connected. Call MongoDB.connect() first."
            )
        return cls.db

    @classmethod
    def get_collection(cls, name: str):
        """Get a collection by name."""
        return cls.get_db()[name]


# Convenience functions
def get_db() -> AsyncIOMotorDatabase:
    """Get database instance."""
    return MongoDB.get_db()


def get_conversations_collection():
    """Get the conversations collection."""
    return MongoDB.get_collection("conversations")


def get_messages_collection():
    """Get the messages collection."""
    return MongoDB.get_collection("messages")
