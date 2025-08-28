import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from core.agent import AIAgent, AgentTool, A2AMessage, A2AResponse
from utils.a2a_mock import A2AServer, A2AClient
from core.config import settings

COORDINATOR_SYSTEM_PROMPT = """
You are the A2A Coordinator Agent for a multi-agent system managing DevOps, SecOps, and FinOps operations.

Your role is to:
- Understand user requests and route them to appropriate specialized agents
- Coordinate between multiple agents when needed
- Provide helpful responses about system status and capabilities
- Translate technical responses into user-friendly language

Available agents and their capabilities:
- DevOps Agent (Alex): System monitoring, infrastructure management, performance optimization
- SecOps Agent (Jordan): Security monitoring, threat detection, incident response  
- FinOps Agent (Casey): Cost analysis, resource optimization, budget planning

When a user asks about:
- System performance, resources, infrastructure -> Use DevOps agent
- Security, threats, vulnerabilities -> Use SecOps agent  
- Costs, optimization, budgets -> Use FinOps agent
- General overview -> Coordinate with all relevant agents

Always be helpful, professional, and explain what you're doing. If you need to call other agents, mention that you're checking with the appropriate team.
"""

coordinator_tools = [
    AgentTool(
        name="call_devops_agent",
        description="Call the DevOps agent for system monitoring and infrastructure questions",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "The method to call on the DevOps agent",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters for the method call",
                },
            },
            "required": ["method"],
        },
    ),
    AgentTool(
        name="call_secops_agent",
        description="Call the SecOps agent for security monitoring and threat detection",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "The method to call on the SecOps agent",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters for the method call",
                },
            },
            "required": ["method"],
        },
    ),
    AgentTool(
        name="call_finops_agent",
        description="Call the FinOps agent for cost analysis and resource optimization",
        parameters={
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "The method to call on the FinOps agent",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters for the method call",
                },
            },
            "required": ["method"],
        },
    ),
    AgentTool(
        name="get_agent_status",
        description="Get the status of all agents in the system",
        parameters={"type": "object", "properties": {}},
    ),
]


class CoordinatorAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="coordinator-agent-001",
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            tools=coordinator_tools,
        )

    async def _execute_tool(self, tool_call) -> Dict[str, Any]:
        function_name = tool_call.function.name
        kwargs = json.loads(tool_call.function.arguments)
        print(f"Coordinator executing tool: {function_name} with args: {kwargs}")

        try:
            if function_name == "call_devops_agent":
                return await self._call_agent(
                    "devops",
                    kwargs.get("method", "get_system_metrics"),
                    kwargs.get("params", {}),
                )
            elif function_name == "call_secops_agent":
                return await self._call_agent(
                    "secops",
                    kwargs.get("method", "get_security_alerts"),
                    kwargs.get("params", {}),
                )
            elif function_name == "call_finops_agent":
                return await self._call_agent(
                    "finops",
                    kwargs.get("method", "get_resource_costs"),
                    kwargs.get("params", {}),
                )
            elif function_name == "get_agent_status":
                return await self._get_agent_status()
            else:
                return {"error": f"Tool '{function_name}' not found."}
        except Exception as e:
            return {"error": f"Error executing {function_name}: {str(e)}"}

    async def _call_agent(
        self, agent_type: str, method: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a specific agent"""
        try:
            # Map agent types to ports (from docker-compose setup)
            agent_ports = {"devops": 8082, "secops": 8083, "finops": 8084}

            if agent_type not in agent_ports:
                return {"error": f"Unknown agent type: {agent_type}"}

            client = A2AClient(f"http://localhost:{agent_ports[agent_type]}")
            result = await client.call(method, params)
            return {
                "success": True,
                "result": result,
                "agent": agent_type,
                "method": method,
            }

        except Exception as e:
            return {"error": f"Failed to contact {agent_type} agent: {str(e)}"}

    async def _get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        agents = ["devops", "secops", "finops"]
        statuses = {}

        for agent in agents:
            try:
                result = await self._call_agent(agent, "get_system_metrics", {})
                statuses[agent] = "online" if result.get("success") else "error"
            except:
                statuses[agent] = "offline"

        return {"agent_statuses": statuses}

    async def handle_chat_message(self, message: str) -> str:
        """Handle a chat message from the user"""
        try:
            # Create A2A message for processing
            chat_message = A2AMessage(
                sender_id="user-chat",
                receiver_id=self.agent_id,
                method="chat_request",
                params={"message": message},
                conversation_id=f"chat-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )

            # Process with AI reasoning
            response = await self.process_message(chat_message)
            return response.response or "I'm sorry, I couldn't process your request."

        except Exception as e:
            return f"I encountered an error: {str(e)}"


# Host agent methods for A2A server
async def handle_chat(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle chat requests from the web interface"""
    coordinator = CoordinatorAgent()
    user_message = message_data.get("message", "")

    if not user_message:
        return {"response": "Please provide a message."}

    try:
        response = await coordinator.handle_chat_message(user_message)
        return {"response": response}
    except Exception as e:
        return {"response": f"I'm sorry, I encountered an error: {str(e)}"}


# Main server setup
async def start_coordinator_server():
    """Start the coordinator agent server"""
    coordinator = CoordinatorAgent()
    server = A2AServer()

    # Register chat handler
    @server.method("chat")
    async def chat_handler(message_data: Dict[str, Any]) -> Dict[str, Any]:
        return await handle_chat(message_data)

    # Register other coordination methods
    @server.method("get_system_overview")
    async def get_system_overview() -> Dict[str, Any]:
        """Get overview from all agents"""
        try:
            # Coordinate with all agents
            devops_result = await coordinator._call_agent(
                "devops", "get_system_metrics", {}
            )
            secops_result = await coordinator._call_agent(
                "secops", "get_security_alerts", {}
            )
            finops_result = await coordinator._call_agent(
                "finops", "get_resource_costs", {}
            )

            return {
                "overview": "System Overview",
                "devops": devops_result,
                "secops": secops_result,
                "finops": finops_result,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": f"Failed to get system overview: {str(e)}"}

    print(
        f"Starting Coordinator Agent server on {settings.a2a_host}:{settings.a2a_port}"
    )
    await server.start(host=settings.a2a_host, port=settings.a2a_port)


if __name__ == "__main__":
    asyncio.run(start_coordinator_server())
