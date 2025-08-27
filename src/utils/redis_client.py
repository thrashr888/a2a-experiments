
import redis.asyncio as redis
import json
from typing import List, Dict, Any

from core.config import settings

class RedisClient:
    """
    An asynchronous client for interacting with Redis to store and retrieve conversation history.
    """
    def __init__(self, redis_url: str = settings.redis_url):
        """
        Initializes the Redis client and connection pool.
        """
        self.redis_url = redis_url
        self._pool = None
        self._client = None
    
    async def _get_client(self):
        """
        Lazy initialization of Redis client to avoid event loop issues.
        """
        if self._client is None:
            self._pool = redis.ConnectionPool.from_url(self.redis_url, decode_responses=True)
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client

    async def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the entire conversation history for a given ID.

        Args:
            conversation_id: The unique identifier for the conversation.

        Returns:
            A list of message dictionaries, or an empty list if not found.
        """
        client = await self._get_client()
        history_json = await client.lrange(conversation_id, 0, -1)
        return [json.loads(message) for message in reversed(history_json)]

    async def add_message_to_history(self, conversation_id: str, message: Dict[str, Any]):
        """
        Adds a new message to the conversation history.

        Args:
            conversation_id: The unique identifier for the conversation.
            message: The message dictionary to add.
        """
        client = await self._get_client()
        await client.lpush(conversation_id, json.dumps(message))

    async def close(self):
        """
        Closes the Redis connection pool.
        """
        if self._pool:
            await self._pool.disconnect()

# Global Redis client instance
redis_client = RedisClient()
