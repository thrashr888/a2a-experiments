from openai import AsyncOpenAI
from typing import List, Dict, Any
from dataclasses import dataclass
import json
import uuid

from a2a.server.agent_execution import AgentExecutor
from a2a.server.events import EventQueue
from a2a.server.agent_execution.context import RequestContext
from agents.memory.session import SQLiteSession
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
                "parameters": self.parameters,
            },
        }


class AIAgent:
    def __init__(self, agent_id: str, system_prompt: str, tools: List[AgentTool]):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.tools = tools
        self._client = None
        import os

        # Ensure data directory exists
        os.makedirs(settings.data_dir, exist_ok=True)
        db_path = os.path.join(settings.data_dir, f"{agent_id}_session.db")
        self.session = SQLiteSession(session_id=agent_id, db_path=db_path)

    def _get_client(self):
        """Lazy initialization of OpenAI client to avoid event loop issues"""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def _execute_tool(self, tool_call, conversation_id: str, user_auth_token: str = None):
        # A concrete agent must implement this method.
        raise NotImplementedError("Agents must implement the _execute_tool method.")
    
    async def request_clarification(self, question: str, context_id: str, event_queue: EventQueue = None):
        """Request clarification from user (A2A multiturn pattern)"""
        if event_queue:
            from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState, Message, TextPart
            
            clarification_message = Message(
                message_id=str(uuid.uuid4()),
                role="agent",
                parts=[TextPart(kind="text", text=question)]
            )
            
            # Set task to input_required state
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context_id,
                    context_id=context_id,
                    final=False,
                    status=TaskStatus(state=TaskState.input_required, message=clarification_message)
                )
            )
            
            return True
        return False
    
    def to_a2a_message(self, context: RequestContext) -> 'A2AMessage':
        """Convert A2A SDK RequestContext to our A2AMessage format"""
        user_input = context.get_user_input()
        return A2AMessage(
            sender_id=getattr(context.call_context.user, 'id', 'client') if context.call_context and hasattr(context.call_context, "user") else "client",
            receiver_id=self.agent_id,
            method="process_user_message", 
            params={"text": user_input},
            conversation_id=context.context_id or context.task_id or "unknown"
        )
    
    async def process_native_a2a_message(self, context: RequestContext, event_queue: EventQueue):
        """Enhanced method using native A2A types for future migration"""
        from a2a.types import Message, TextPart, TaskStatusUpdateEvent, TaskStatus, TaskState
        
        user_input = context.get_user_input()
        
        # Example of working with native A2A Message types
        incoming_message = context.message
        if incoming_message and incoming_message.parts:
            # Process native A2A message parts directly
            text_parts = [part.text for part in incoming_message.parts if hasattr(part, 'text')]
            combined_text = " ".join(text_parts)
            
            # Use native A2A responses 
            response_message = Message(
                message_id=str(uuid.uuid4()),
                role="agent",
                parts=[TextPart(kind="text", text=f"Processed: {combined_text}")]
            )
            
            return response_message
        
        return None

    async def process_message(self, message: A2AMessage, user_auth_token: str = None) -> A2AResponse:
        """Process incoming A2A message with AI reasoning"""
        try:
            history_items = await self.session.get_items()
            # Convert history items to OpenAI format, preserving tool_calls and tool_call_id
            history = []
            for item in history_items:
                msg = {
                    "role": item.get("role", "user"),
                    "content": item.get("content", ""),
                }
                # Preserve tool_calls for assistant messages
                if item.get("tool_calls"):
                    msg["tool_calls"] = item["tool_calls"]
                # Preserve tool_call_id for tool messages
                if item.get("tool_call_id"):
                    msg["tool_call_id"] = item["tool_call_id"]
                    msg["name"] = item.get("name", "unknown_tool")
                history.append(msg)

            user_message_content = (
                f"Method: {message.method}, Params: {json.dumps(message.params)}"
            )
            await self.session.add_items(
                [{"role": "user", "content": user_message_content}]
            )

            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                    + "\n\nProvide concise, professional responses.",
                },
                *history,
                {"role": "user", "content": user_message_content},
            ]

            client = self._get_client()
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=[tool.to_openai_function() for tool in self.tools],
                tool_choice="auto",
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            tool_results = []

            await self.session.add_items(
                [
                    {
                        "role": "assistant",
                        "content": response_message.content or "",
                        "tool_calls": [tc.dict() for tc in tool_calls or []],
                    }
                ]
            )

            if tool_calls:
                messages.append(response_message)
                for tool_call in tool_calls:
                    result = await self._execute_tool(
                        tool_call, message.conversation_id, user_auth_token
                    )
                    tool_results.append(result)
                    # Extract the actual response content for better display
                    tool_content = result
                    if isinstance(result, dict):
                        if "response" in result:
                            tool_content = result["response"]
                        elif "error" in result:
                            tool_content = f"Error: {result['error']}"
                        else:
                            tool_content = json.dumps(result)
                    
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": str(tool_content),
                        }
                    )
                    await self.session.add_items(
                        [
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": str(tool_content),
                            }
                        ]
                    )

                client = self._get_client()
                final_response = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                )
                final_text_response = final_response.choices[0].message.content
                await self.session.add_items(
                    [{"role": "assistant", "content": final_text_response}]
                )
            else:
                final_text_response = response_message.content

            return A2AResponse(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                conversation_id=message.conversation_id,
                response=final_text_response,
                data={"tool_results": tool_results},
                tool_calls=[tc.function.dict() for tc in tool_calls or []],
            )
        except Exception as e:
            import traceback

            print(f"Error processing message: {e}\n{traceback.format_exc()}")
            return A2AResponse(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                conversation_id=message.conversation_id,
                response=f"An internal error occurred: {e}",
                data={"error": True, "details": traceback.format_exc()},
                confidence=0.0,
            )


class AI_AgentExecutor(AgentExecutor):
    def __init__(self, agent: AIAgent):
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """Execute agent request using A2A protocol"""
        # Extract message from context
        incoming_message = context.message

        if not incoming_message:
            # No message to process - this shouldn't happen
            from a2a.types import TaskStatusUpdateEvent, TaskStatus, TaskState

            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id or "unknown",
                    context_id=context.context_id or "unknown",
                    final=True,
                    status=TaskStatus(state=TaskState.failed),
                )
            )
            return

        # Get user input text from message parts
        user_input = context.get_user_input()

        # Convert to our A2AMessage format using helper method
        message = self.agent.to_a2a_message(context)
        
        # Extract end-user authentication from message metadata (enterprise-ready pattern)
        user_auth_token = None
        
        # Try to get token from message metadata first
        if hasattr(context, 'message') and context.message and hasattr(context.message, 'metadata'):
            if context.message.metadata and 'auth_token' in context.message.metadata:
                user_auth_token = context.message.metadata['auth_token']
        
        # Fallback to HTTP headers if available  
        if not user_auth_token and context.call_context and hasattr(context.call_context, 'request'):
            auth_header = context.call_context.request.headers.get('authorization', '')
            if auth_header.startswith('Bearer '):
                user_auth_token = auth_header[7:]  # Remove 'Bearer ' prefix

        # Send initial progress update (A2A streaming pattern)
        from a2a.types import (
            TaskStatusUpdateEvent,
            TaskStatus,
            TaskState,
            Message,
            TextPart,
        )
        
        import uuid
        initial_message = Message(
            message_id=str(uuid.uuid4()),
            role="agent", 
            parts=[TextPart(kind="text", text=f"🔄 {self.agent.agent_id} is processing your request...")]
        )
        
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id or "unknown",
                context_id=context.context_id or "unknown", 
                final=False,
                status=TaskStatus(state=TaskState.working, message=initial_message)
            )
        )

        # Process the message with end-user authentication
        response = await self.agent.process_message(message, user_auth_token)

        # Check if authentication is required
        auth_required = False
        auth_info = None
        if response.data and response.data.get("tool_results"):
            for tool_result in response.data["tool_results"]:
                if isinstance(tool_result, dict) and tool_result.get("auth_required"):
                    auth_required = True
                    auth_info = {
                        "auth_required": True,
                        "auth_message": tool_result.get("auth_message", "Authentication required"),
                        "auth_url": tool_result.get("auth_url", ""),
                        "service": "GitHub"
                    }
                    break

        # Determine task state based on auth requirements
        if auth_required:
            task_state = TaskState.input_required
            response_text = response.response + "\n\n🔐 **Authentication Required**: Please provide your GitHub Personal Access Token to continue."
        else:
            task_state = TaskState.completed
            response_text = response.response

        # Send TaskArtifactUpdateEvent with the response (A2A streaming pattern)
        from a2a.types import TaskArtifactUpdateEvent, Artifact, TextPart
        
        # Create artifact with agent's response
        response_artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            name=f"Response from {self.agent.agent_id}",
            description="Agent response",
            parts=[TextPart(kind="text", text=response_text)]
        )
        
        # Send artifact update event
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=context.task_id or "unknown",
                context_id=context.context_id or "unknown",
                artifact=response_artifact
            )
        )

        # Create a Message object with the agent's response
        response_message = Message(
            message_id=str(uuid.uuid4()),
            role="agent",
            parts=[TextPart(kind="text", text=response_text)],
        )

        # Add auth info to message metadata if auth is required
        if auth_required and auth_info:
            # Store auth info in response data for UI to access
            response.data = response.data or {}
            response.data["auth_info"] = auth_info

        # Create TaskStatus with the response message
        task_status = TaskStatus(state=task_state, message=response_message)

        # Send the status update event
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id or "unknown",
                context_id=context.context_id or "unknown",
                final=True,
                status=task_status,
            )
        )

    async def cancel(self):
        """Cancel any running operations (required by AgentExecutor interface)"""
        # For now, we don't have any cancellable operations
        pass
