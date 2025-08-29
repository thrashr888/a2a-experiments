from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from datetime import datetime
import json
import os
import asyncio
from openai import AsyncOpenAI

from core.agent_registry import registry
from core.config import settings
from web.utils import safe_template_response

router = APIRouter(prefix="/api", tags=["chat"])


class SimpleChatHistory:
    """Simple file-based chat history manager"""

    def __init__(self):
        self.history_dir = os.path.join(settings.data_dir, "chat_history")
        os.makedirs(self.history_dir, exist_ok=True)
        self._lock = asyncio.Lock()

    def _get_history_file(self, conversation_id: str) -> str:
        return os.path.join(self.history_dir, f"{conversation_id}.json")

    async def add_message(self, conversation_id: str, message: dict):
        """Add a message to conversation history"""
        async with self._lock:
            history_file = self._get_history_file(conversation_id)

            # Load existing history
            messages = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r") as f:
                        messages = json.load(f)
                except:
                    messages = []

            # Add new message
            messages.append(message)

            # Keep only last 50 messages to prevent unbounded growth
            if len(messages) > 50:
                messages = messages[-50:]

            # Save back to file
            try:
                with open(history_file, "w") as f:
                    json.dump(messages, f, indent=2)
            except Exception as e:
                print(f"Error saving chat history: {e}")

    async def get_history(self, conversation_id: str) -> list:
        """Get conversation history"""
        history_file = self._get_history_file(conversation_id)

        if not os.path.exists(history_file):
            return []

        try:
            with open(history_file, "r") as f:
                messages = json.load(f)

            # Return last 20 messages for UI
            return messages[-20:] if len(messages) > 20 else messages
        except:
            return []

    async def clear_history(self, conversation_id: str):
        """Clear conversation history"""
        history_file = self._get_history_file(conversation_id)
        try:
            if os.path.exists(history_file):
                os.remove(history_file)
        except Exception as e:
            print(f"Error clearing chat history: {e}")


# Initialize chat history manager
chat_history = SimpleChatHistory()


class A2ATaskRouter:
    """Proper A2A protocol router that determines which specialist agent should handle each task"""

    def __init__(self):
        self._openai_client = None

    def _get_openai_client(self):
        """Lazy initialization of OpenAI client to avoid event loop issues"""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    async def get_agent_capabilities(self) -> dict:
        """Get agent capabilities for routing decisions"""
        agents = await registry.list_agents()

        capabilities = {}
        for agent in agents:
            if agent.agent_type.value != "host":
                capabilities[agent.name] = {
                    "endpoint": agent.endpoint,
                    "description": agent.description,
                    "capabilities": agent.capabilities or [],
                    "agent_id": agent.id,
                }

        return capabilities

    async def determine_best_agent(self, user_message: str) -> tuple[str, str]:
        """Use AI to determine which agent should handle this request"""
        capabilities = await self.get_agent_capabilities()

        if not capabilities:
            return None, "No specialist agents available"

        agents_info = []
        for name, info in capabilities.items():
            caps = (
                ", ".join(info["capabilities"])
                if info["capabilities"]
                else "general tasks"
            )
            agents_info.append(
                f"- {name}: {info['description']} (Capabilities: {caps})"
            )

        system_prompt = f"""
You are an A2A task router. Analyze the user's request and determine which single specialist agent is best suited to handle it.

Available agents:
{chr(10).join(agents_info)}

ROUTING RULES:
- Infrastructure/DevOps/system performance/monitoring → Infrastructure Monitor (Alex)
- Security/threats/vulnerabilities/alerts → Security Monitor (Jordan)  
- Costs/budgets/financial optimization/spending → Cost Monitor (Casey)
- Containers/container management → ContainerOps (Morgan)
- DataOps/database queries/schema inspection → DataOps (Dana)
- Git/GitHub/repositories/CI-CD → GitOps (Riley)

Respond with ONLY the agent name (exactly as listed above), nothing else.
If no agent fits perfectly, choose the closest match.
"""

        try:
            client = self._get_openai_client()
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # Use faster model for routing
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=20,
                temperature=0,
            )

            agent_name = response.choices[0].message.content.strip()

            if agent_name in capabilities:
                return agent_name, capabilities[agent_name]["endpoint"]
            else:
                # Fallback to first available agent
                first_agent = list(capabilities.keys())[0]
                return first_agent, capabilities[first_agent]["endpoint"]

        except Exception as e:
            print(f"Error in agent routing: {e}")
            # Fallback to first available agent
            first_agent = list(capabilities.keys())[0]
            return first_agent, capabilities[first_agent]["endpoint"]


async def render_agent_message(agent_name: str, content: str, request: Request) -> str:
    """Render individual agent message using component template"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    context = {"agent_name": agent_name, "content": content, "timestamp": timestamp}

    # Save agent response to chat history
    await chat_history.add_message(
        "main_chat",
        {
            "role": "assistant",
            "agent_name": agent_name,
            "content": content,
            "timestamp": timestamp,
        },
    )

    response = safe_template_response("components/agent_message.html", request, context)
    return response.body.decode()


async def render_agent_error(
    agent_name: str, error_message: str, request: Request
) -> str:
    """Render agent error message using component template"""
    context = {
        "agent_name": agent_name,
        "error_message": error_message,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    response = safe_template_response(
        "components/agent_error_message.html", request, context
    )
    return response.body.decode()


async def render_auth_prompt(agent_name: str, response_text: str, auth_info: dict, request: Request):
    """Render authentication prompt using component template"""
    context = {
        "agent_name": agent_name,
        "content": response_text,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "auth_service": auth_info.get("service", "GitHub"),
        "auth_message": auth_info.get("auth_message", "Authentication required"),
        "auth_url": auth_info.get("auth_url", "https://github.com/settings/tokens"),
    }
    response = safe_template_response(
        "components/auth_prompt.html", request, context
    )
    return response.body.decode()


async def route_to_specialist_agent(
    conversation_id: str, user_message: str, html_parts: list, request: Request
):
    """Route user message to the most appropriate specialist agent using A2A protocol"""

    router = A2ATaskRouter()

    try:
        # Determine which agent should handle this request
        agent_name, agent_endpoint = await router.determine_best_agent(user_message)
        print(f"🎯 ROUTING: '{user_message}' → {agent_name} at {agent_endpoint}")

        if not agent_name:
            error_html = await render_agent_error(
                "🤖 Task Router", "No specialist agents available", request
            )
            html_parts.append(error_html)
            return

        import httpx

        # Call the selected agent using A2A JSON-RPC protocol
        message_parts = [{"kind": "text", "text": user_message}]

        # Get auth header for both metadata and headers
        auth_header = request.headers.get('authorization')

        # Include auth token in message metadata if available
        message_metadata = {}
        if auth_header and auth_header.startswith('Bearer '):
            message_metadata["auth_token"] = auth_header[7:]  # Remove 'Bearer ' prefix

        jsonrpc_payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": f"msg-{conversation_id}-{datetime.now().timestamp()}",
                    "role": "user",
                    "parts": message_parts,
                    "metadata": message_metadata if message_metadata else None,
                }
            },
            "id": f"request-{datetime.now().timestamp()}",
        }

        # Prepare headers, including any Authorization header from the request
        headers = {"Content-Type": "application/json"}
        if auth_header:
            headers['Authorization'] = auth_header

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{agent_endpoint}/",
                json=jsonrpc_payload,
                headers=headers,
                timeout=45.0,
            )

            if response.status_code == 200:
                result = response.json()
                print(f"A2A Response from {agent_name}: {result}")

                # Check for JSON-RPC success result
                if "result" in result and result.get("result"):
                    json_result = result["result"]
                    # Check for A2A Task response with status.message
                    if "status" in json_result and "message" in json_result["status"]:
                        status_message = json_result["status"]["message"]
                        if (
                            "parts" in status_message
                            and len(status_message["parts"]) > 0
                        ):
                            response_text = status_message["parts"][0].get(
                                "text", "No response"
                            )
                            
                            # Check if this response requires authentication
                            task_status = json_result.get("status", {})
                            requires_auth = task_status.get("state") == "input_required"
                            auth_info = None
                            
                            # Look for auth info in the response data or artifacts
                            if requires_auth:
                                # Check for auth info in artifacts or task data
                                artifacts = json_result.get("artifacts", [])
                                for artifact in artifacts:
                                    if artifact.get("auth_required"):
                                        auth_info = {
                                            "auth_required": True,
                                            "auth_message": artifact.get("auth_message", "Authentication required"),
                                            "auth_url": artifact.get("auth_url", "https://github.com/settings/tokens"),
                                            "service": artifact.get("service", "GitHub")
                                        }
                                        break
                                
                                # Also check for auth info in response text patterns
                                if not auth_info and "Authentication Required" in response_text:
                                    auth_info = {
                                        "auth_required": True,
                                        "auth_message": "Please provide your GitHub Personal Access Token to continue",
                                        "auth_url": "https://github.com/settings/tokens",
                                        "service": "GitHub"
                                    }
                            
                            # Render appropriate component
                            if requires_auth and auth_info:
                                # Render authentication prompt
                                agent_html = await render_auth_prompt(
                                    agent_name, response_text, auth_info, request
                                )
                            else:
                                # Render normal agent message
                                agent_html = await render_agent_message(
                                    agent_name, response_text, request
                                )
                            html_parts.append(agent_html)
                        else:
                            error_html = await render_agent_error(
                                agent_name, "No message content in response.", request
                            )
                            html_parts.append(error_html)
                    else:
                        error_html = await render_agent_error(
                            agent_name, "Invalid A2A response format.", request
                        )
                        html_parts.append(error_html)
                elif "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    error_html = await render_agent_error(
                        agent_name, f"Agent error: {error_msg}", request
                    )
                    html_parts.append(error_html)
                else:
                    error_html = await render_agent_error(
                        agent_name, "Unexpected response format.", request
                    )
                    html_parts.append(error_html)
            else:
                error_html = await render_agent_error(
                    agent_name, "Failed to contact.", request
                )
                html_parts.append(error_html)

    except Exception as e:
        print(f"Error in specialist agent routing: {e}")
        error_html = await render_agent_error(
            "🤖 Task Router", f"Routing error: {str(e)}", request
        )
        html_parts.append(error_html)


# Global task router instance - lazy initialized
task_router = None


def get_task_router():
    """Lazy initialization of A2A task router to avoid event loop issues"""
    global task_router
    if task_router is None:
        task_router = A2ATaskRouter()
    return task_router


@router.post("/chat", response_class=HTMLResponse)
async def chat_with_agents(request: Request):
    """Handle chat messages with proper A2A streaming multiturn pattern"""
    form = await request.form()
    user_message = form.get("message", "").strip()

    if not user_message:
        return ""

    conversation_id = "main_chat"

    try:
        # Get timestamp for user message
        user_time = datetime.now().strftime("%H:%M:%S")

        # Save user message to file-based history
        await chat_history.add_message(
            conversation_id,
            {"role": "user", "content": user_message, "timestamp": user_time},
        )

        # Create HTML for user message using template
        html_parts = []
        user_context = {"content": user_message, "timestamp": user_time}
        user_html_response = safe_template_response(
            "components/user_message.html", request, user_context
        )
        html_parts.append(user_html_response.body.decode())

        # Route to the most appropriate specialist agent
        await route_to_specialist_agent(
            conversation_id, user_message, html_parts, request
        )

        # Return all messages as HTML
        return "".join(html_parts)

    except Exception as e:
        error_time = datetime.now().strftime("%H:%M:%S")
        context = {
            "user_message": user_message,
            "user_time": user_time,
            "assistant_response": f"I apologize, but I encountered an error: {str(e)}",
            "assistant_time": error_time,
        }

    return safe_template_response("components/chat_messages.html", request, context)


@router.get("/chat/history", response_class=HTMLResponse)
async def get_chat_history(request: Request):
    """Load chat history from file-based storage"""
    conversation_id = "main_chat"

    try:
        history = await chat_history.get_history(conversation_id)
        context = {"messages": history}
    except Exception as e:
        print(f"Error loading chat history: {e}")
        context = {"messages": []}

    return safe_template_response("components/chat_history.html", request, context)


@router.post("/chat/clear", response_class=HTMLResponse)
async def clear_chat_history(request: Request):
    """Clear chat history from file-based storage"""
    conversation_id = "main_chat"

    try:
        await chat_history.clear_history(conversation_id)
        context = {"messages": []}
    except Exception as e:
        print(f"Error clearing chat history: {e}")
        context = {"messages": []}

    return safe_template_response("components/chat_history.html", request, context)
