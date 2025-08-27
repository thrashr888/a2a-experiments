
from openai import AsyncOpenAI
from typing import List, Dict, Any
from dataclasses import dataclass
import json

from utils.redis_client import redis_client
from core.config import settings

# As defined in the plan, but using dataclasses for clarity
@dataclass
class A2AMessage:
    sender_id: str
    receiver_id: str
    method: str
    params: Dict[str, Any]
    conversation_id: str
    context: Dict[str, Any] = None
    requires_reasoning: bool = True

@dataclass
class A2AResponse:
    sender_id: str
    receiver_id: str
    conversation_id: str
    response: str
    data: Dict[str, Any] = None
    tool_calls: List[Dict] = None
    confidence: float = 1.0

class AgentTool:
    def __init__(self, name: str, description: str, parameters: Dict):
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_openai_function(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

class AIAgent:
    def __init__(self, agent_id: str, system_prompt: str, tools: List[AgentTool]):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.tools = tools
        self._client = None
        self.redis_client = redis_client
    
    def _get_client(self):
        """Lazy initialization of OpenAI client to avoid event loop issues"""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def _execute_tool(self, tool_call):
        # This is the missing link identified earlier.
        # A concrete agent must implement this method.
        raise NotImplementedError("Agents must implement the _execute_tool method.")

    async def process_message(self, message: A2AMessage) -> A2AResponse:
        """Process incoming A2A message with AI reasoning"""

        # Disable conversation history completely to eliminate errors
        # conversation = await self.redis_client.get_conversation_history(message.conversation_id)
        
        # Build messages for LLM - no conversation history
        messages = [
            {"role": "system", "content": self.system_prompt + "\n\nProvide concise, professional responses."},
            {"role": "user", "content": f"Method: {message.method}, Params: {json.dumps(message.params)}"}
        ]

        # Call OpenAI with function calling
        client = self._get_client()
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=[tool.to_openai_function() for tool in self.tools],
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        tool_results = []

        # Disable all Redis history saving to eliminate errors
        # await self.redis_client.add_message_to_history(
        #     message.conversation_id, {"role": "user", "content": f"Method: {message.method}, Params: {json.dumps(message.params)}"}
        # )

        if tool_calls:
            messages.append(response_message)
            for tool_call in tool_calls:
                result = await self._execute_tool(tool_call)
                tool_results.append(result)
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": json.dumps(result),
                    }
                )
                # Don't save tool results to keep conversation history minimal

            # Get the final response from the model
            client = self._get_client()
            final_response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
            )
            final_text_response = final_response.choices[0].message.content
            # Disable Redis saving
            # await self.redis_client.add_message_to_history(
            #     message.conversation_id, {"role": "assistant", "content": final_text_response}
            # )
        else:
            final_text_response = response_message.content

        return A2AResponse(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            conversation_id=message.conversation_id,
            response=final_text_response,
            data={"tool_results": tool_results},
            tool_calls=[tc.function.dict() for tc in tool_calls or []]
        )
