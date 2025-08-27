
import redis.asyncio as redis
import json
from typing import List, Dict, Any

from src.core.config import settings

class RedisClient:
    """
    An asynchronous client for interacting with Redis to store and retrieve conversation history.
    """
    def __init__(self, redis_url: str = settings.redis_url):
        """
        Initializes the Redis client and connection pool.
        """
        self.pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        self.client = redis.Redis(connection_pool=self.pool)

    async def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the entire conversation history for a given ID.

        Args:
            conversation_id: The unique identifier for the conversation.

        Returns:
            A list of message dictionaries, or an empty list if not found.
        """
        history_json = await self.client.lrange(conversation_id, 0, -1)
        return [json.loads(message) for message in reversed(history_json)]

    async def add_message_to_history(self, conversation_id: str, message: Dict[str, Any]):
        """
        Adds a new message to the conversation history.

        Args:
            conversation_id: The unique identifier for the conversation.
            message: The message dictionary to add.
        """
        await self.client.lpush(conversation_id, json.dumps(message))

    async def close(self):
        """
        Closes the Redis connection pool.
        """
        await self.pool.disconnect()

# Global Redis client instance
redis_client = RedisClient()
