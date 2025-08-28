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


class AICoordinator:
    """AI-powered coordinator that dynamically discovers and routes to available A2A agents"""

    def __init__(self):
        self._openai_client = None

    def _get_openai_client(self):
        """Lazy initialization of OpenAI client to avoid event loop issues"""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    async def get_dynamic_system_prompt(self) -> str:
        """Generate system prompt based on currently registered agents"""
        agents = await registry.list_agents()

        agent_descriptions = []
        for agent in agents:
            if agent.agent_type.value != "host":  # Skip the host agent itself
                capabilities_list = (
                    ", ".join(agent.capabilities)
                    if agent.capabilities
                    else "general tasks"
                )
                agent_descriptions.append(
                    f"- {agent.name}: {agent.description}\n  - Capabilities: {capabilities_list}"
                )

        agents_text = (
            "\n".join(agent_descriptions)
            if agent_descriptions
            else "No specialized agents currently available."
        )

        return f"""
You are the A2A Coordinator Agent for a multi-agent system. Your role is to:
1. Understand user requests and determine which specialist agents to contact
2. Call the appropriate A2A agents using available tools  
3. Provide the agent responses directly without excessive commentary

Currently available agents:
{agents_text}

IMPORTANT INSTRUCTIONS:
- Be concise and direct in your responses
- When agents return data, present it cleanly without excessive narrative
- If multiple agents are called, present each result separately and clearly
- Avoid repeating the same information multiple times
- Do not generate long explanatory text about what you're doing
- Present agent responses as they are, with minimal wrapper text

Use the call_agent function to contact any of the available agents with appropriate method names.
"""

    async def get_dynamic_tools(self) -> list:
        """Generate tool definitions based on currently registered agents"""
        agents = await registry.list_agents()
        tools = []

        # Add a generic call_agent tool that can route to any registered agent
        available_agents = [
            agent.name for agent in agents if agent.agent_type.value != "host"
        ]
        agent_endpoints = {
            agent.name: agent.endpoint
            for agent in agents
            if agent.agent_type.value != "host"
        }

        if available_agents:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "call_agent",
                        "description": f"Call any of the available agents: {', '.join(available_agents)}",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "agent_name": {
                                    "type": "string",
                                    "description": f"Name of the agent to call. Available: {', '.join(available_agents)}",
                                    "enum": available_agents,
                                },
                                "method": {
                                    "type": "string",
                                    "description": "The method to call on the agent",
                                },
                                "params": {
                                    "type": "object",
                                    "description": "Parameters for the method call",
                                    "default": {},
                                },
                            },
                            "required": ["agent_name", "method"],
                        },
                    },
                }
            )

        # Store agent endpoints for routing
        self.agent_endpoints = agent_endpoints
        return tools

    async def call_agent_by_name(
        self, agent_name: str, method: str, params: dict = None
    ) -> dict:
        """Call a specific A2A agent by name using dynamic endpoint lookup"""
        if (
            not hasattr(self, "agent_endpoints")
            or agent_name not in self.agent_endpoints
        ):
            return {"error": f"Agent '{agent_name}' not found in registry"}

        endpoint = self.agent_endpoints[agent_name]

        try:
            # Use simple HTTP POST to agent endpoint
            import httpx

            payload = {"method": method}
            if params:
                payload.update(params)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{endpoint}/process", json=payload, timeout=15.0
                )
                response.raise_for_status()
                result = response.json()

            return {"success": True, "result": result, "agent": agent_name}

        except Exception as e:
            return {"error": f"Failed to contact {agent_name}: {str(e)}"}

    async def execute_tool_call(self, tool_call):
        """Execute a tool call from the LLM"""
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        if function_name == "call_agent":
            return await self.call_agent_by_name(
                arguments["agent_name"],
                arguments["method"],
                arguments.get("params", {}),
            )
        else:
            return {"error": f"Unknown tool: {function_name}"}

    async def process_message(self, user_message: str) -> str:
        """Process user message using AI reasoning and dynamic agent coordination"""
        try:
            # Reset OpenAI client to avoid event loop conflicts
            self._openai_client = None
            # Get dynamic system prompt and tools based on current agent registry
            system_prompt = await self.get_dynamic_system_prompt()
            tools = await self.get_dynamic_tools()

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            # Get initial response from OpenAI
            openai_client = self._get_openai_client()
            response = await openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
            )

            response_message = response.choices[0].message

            # If the AI wants to call tools
            if response_message.tool_calls:
                # Add the assistant's message to conversation
                messages.append(response_message)

                tool_results = []

                # Execute tool calls
                for tool_call in response_message.tool_calls:
                    tool_result = await self.execute_tool_call(tool_call)

                    # Debug: Print tool result
                    print(f"Tool result from {tool_call.function.name}: {tool_result}")

                    tool_results.append(tool_result)

                    # Add tool result to conversation
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": json.dumps(tool_result),
                        }
                    )

                # Return individual agent responses separately
                responses = []
                for result in tool_results:
                    if result.get("success") and "result" in result:
                        agent_result = result["result"]
                        if "response" in agent_result:
                            agent_name = (
                                agent_result.get("sender_id", "Unknown Agent")
                                .replace("-", " ")
                                .title()
                            )
                            responses.append(
                                f"**{agent_name}**\n{agent_result['response']}"
                            )
                        elif "message" in agent_result:
                            agent_name = result.get("agent", "Agent")
                            responses.append(
                                f"**{agent_name}**\n{agent_result['message']}"
                            )
                    elif result.get("error"):
                        # Handle agent errors gracefully
                        agent_name = result.get("agent", "Agent")
                        responses.append(f"**{agent_name}**\nFailed to contact.")

                if responses:
                    return "\n\n".join(responses)
                else:
                    return "I wasn't able to contact any of the specialist agents. Please try again."
            else:
                # Direct response without tool calls
                return response_message.content

        except Exception as e:
            return f"I apologize, but I encountered an error: {str(e)}"

    async def process_message_multi_turn(self, user_message: str) -> list:
        """Process user message and return individual agent responses for multi-turn chat"""
        try:
            # Reset OpenAI client to avoid event loop conflicts
            self._openai_client = None

            # Simple approach: directly call each working agent
            agent_responses = []
            working_agents = [
                ("devops", "get_system_metrics", "🏗️ Infrastructure Monitor (Alex)"),
                ("finops", "get_resource_costs", "💰 Cost Monitor (Casey)"),
            ]

            for agent_type, method, display_name in working_agents:
                try:
                    port = 8082 if agent_type == "devops" else 8084
                    import httpx

                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"http://localhost:{port}/process",
                            json={"method": method, "params": {}},
                            timeout=45.0,
                        )
                        if response.status_code == 200:
                            result = response.json()
                            if "response" in result:
                                agent_responses.append(
                                    {
                                        "agent_name": display_name,
                                        "content": result["response"],
                                    }
                                )
                        else:
                            agent_responses.append(
                                {
                                    "agent_name": display_name,
                                    "content": "Failed to contact.",
                                }
                            )
                except Exception as e:
                    agent_responses.append(
                        {"agent_name": display_name, "content": "Failed to contact."}
                    )

            return (
                agent_responses
                if agent_responses
                else [
                    {
                        "agent_name": "🤖 Coordinator Agent",
                        "content": "No agents responded.",
                    }
                ]
            )

        except Exception as e:
            return [
                {
                    "agent_name": "🤖 Coordinator Agent",
                    "content": f"I apologize, but I encountered an error: {str(e)}",
                }
            ]

    def _format_agent_name(self, agent_id: str) -> str:
        """Format agent ID into a readable name"""
        if "devops" in agent_id.lower():
            return "🏗️ Infrastructure Monitor (Alex)"
        elif "secops" in agent_id.lower():
            return "🔒 Security Monitor (Jordan)"
        elif "finops" in agent_id.lower():
            return "💰 Cost Monitor (Casey)"
        else:
            return "🤖 " + agent_id.replace("-", " ").title()


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


async def trigger_agent_contributions(
    conversation_id: str, user_message: str, html_parts: list, request: Request
):
    """Trigger each agent to contribute individually to the conversation (A2A streaming pattern)"""

    # Define all agents and their endpoints
    agents = [
        {
            "name": "🏗️ Infrastructure Monitor (Alex)",
            "port": 8082,
            "method": "get_system_metrics",
            "description": "System performance and health",
        },
        {
            "name": "🔒 Security Monitor (Jordan)",
            "port": 8083,
            "method": "get_security_alerts",
            "description": "Security threats and alerts",
        },
        {
            "name": "💰 Cost Monitor (Casey)",
            "port": 8084,
            "method": "get_resource_costs",
            "description": "Cost analysis and optimization",
        },
        {
            "name": "🐳 Docker Monitor (Morgan)",
            "port": 8085,
            "method": "get_docker_system_info",
            "description": "Docker containers and system monitoring",
        },
    ]

    # Each agent contributes individually (A2A streaming pattern)
    for agent in agents:
        try:
            import httpx

            # Call agent using A2A JSON-RPC protocol
            message_parts = [{"kind": "text", "text": user_message}]

            jsonrpc_payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "messageId": f"msg-{conversation_id}-{datetime.now().timestamp()}",
                        "role": "user",
                        "parts": message_parts,
                    }
                },
                "id": f"request-{datetime.now().timestamp()}",
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://localhost:{agent['port']}/",
                    json=jsonrpc_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=45.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    # Debug: print the response structure
                    print(f"A2A Response from {agent['name']}: {result}")

                    # Check for JSON-RPC success result
                    if "result" in result and result.get("result"):
                        json_result = result["result"]
                        # Check for A2A Task response with status.message
                        if (
                            "status" in json_result
                            and "message" in json_result["status"]
                        ):
                            status_message = json_result["status"]["message"]
                            if (
                                "parts" in status_message
                                and len(status_message["parts"]) > 0
                            ):
                                response_text = status_message["parts"][0].get(
                                    "text", "No response"
                                )
                                # Agent successfully contributed - render with template
                                agent_html = await render_agent_message(
                                    agent["name"], response_text, request
                                )
                                html_parts.append(agent_html)
                            else:
                                # No parts in status message
                                error_html = await render_agent_error(
                                    agent["name"],
                                    "No message content in response.",
                                    request,
                                )
                                html_parts.append(error_html)
                        else:
                            # No status.message field
                            error_html = await render_agent_error(
                                agent["name"], "Invalid A2A response format.", request
                            )
                            html_parts.append(error_html)
                    elif "error" in result:
                        # JSON-RPC error response
                        error_msg = result["error"].get("message", "Unknown error")
                        error_html = await render_agent_error(
                            agent["name"], f"Agent error: {error_msg}", request
                        )
                        html_parts.append(error_html)
                    else:
                        # No result or error field - unexpected response format
                        error_html = await render_agent_error(
                            agent["name"], "Unexpected response format.", request
                        )
                        html_parts.append(error_html)
                else:
                    # HTTP error - render error with template
                    error_html = await render_agent_error(
                        agent["name"], "Failed to contact.", request
                    )
                    html_parts.append(error_html)

        except Exception as e:
            # Exception - render error with template
            error_html = await render_agent_error(
                agent["name"], "Failed to contact.", request
            )
            html_parts.append(error_html)


# Global coordinator instance - lazy initialized
coordinator = None


def get_coordinator():
    """Lazy initialization of coordinator to avoid event loop issues"""
    global coordinator
    if coordinator is None:
        coordinator = AICoordinator()
    return coordinator


@router.post("/chat", response_class=HTMLResponse)
async def chat_with_coordinator(request: Request):
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

        # Start agent loop - each agent contributes individually
        await trigger_agent_contributions(
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
