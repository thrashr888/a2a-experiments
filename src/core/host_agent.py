import asyncio
import json
from typing import Dict, Any, List

from core.agent import AIAgent, AgentTool, A2AMessage
# from utils.a2a_mock import A2AServer, A2AClient  # Disabled to avoid dependency issues
from core.config import settings
from core.agent_registry import registry, AgentCard, AgentType

COORDINATOR_SYSTEM_PROMPT = """
You are Sam, the team lead who coordinates between DevOps, SecOps, and FinOps specialists.

Your role:
- Understand user requests and delegate to appropriate specialists
- Synthesize information from multiple agents
- Provide holistic recommendations
- Facilitate collaboration between specialists
- Present findings in a clear, executive-friendly format

When handling requests:
1. Analyze what expertise is needed (DevOps, SecOps, or FinOps).
2. Use the 'delegate_to_agent' tool to ask the relevant agent for their input.
3. Synthesize the responses from the agents into a coherent recommendation.
4. Always consider cross-functional implications (security + cost + performance).
"""

coordinator_tools = [
    AgentTool(
        name="delegate_to_agent",
        description="Delegate a specific task to a specialized agent (DevOps, SecOps, or FinOps).",
        parameters={
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "description": "The type of agent to delegate to.",
                    "enum": ["DEVOPS", "SECOPS", "FINOPS"]
                },
                "task": {
                    "type": "string",
                    "description": "The specific question or task for the agent."
                }
            },
            "required": ["agent_type", "task"]
        }
    )
]

class CoordinatorAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="coordinator-agent-sam-001",
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            tools=coordinator_tools
        )

    async def _execute_tool(self, tool_call, conversation_id: str) -> Dict[str, Any]:
        function_name = tool_call.function.name
        if function_name == 'delegate_to_agent':
            kwargs = json.loads(tool_call.function.arguments)
            agent_type = AgentType[kwargs["agent_type"]]
            task = kwargs["task"]

            # Find agent in registry
            agents = await registry.find_agents_by_type(agent_type)
            if not agents:
                return {"error": f"No {agent_type.value} agent is available."}
            
            # For simplicity, use the first agent found
            target_agent = agents[0]
            
            print(f"Delegating task '{task}' to {target_agent.name} at {target_agent.endpoint}")

            try:
                # Use simple HTTP client instead of A2AClient
                import httpx
                async with httpx.AsyncClient() as client:
                    message = A2AMessage(
                        sender_id=self.agent_id,
                        receiver_id=target_agent.id,
                        method=task, # Using the task as the method
                        params={},
                        conversation_id=conversation_id # Pass the original conversation_id
                    )
                    response = await client.post(
                        f"{target_agent.endpoint}/process", 
                        json=message.__dict__,
                        timeout=30.0
                    )
                    response_data = response.json() if response.status_code == 200 else {"error": "Failed to contact agent"}
                return response_data
            except Exception as e:
                print(f"Error delegating to agent: {e}")
                return {"error": str(e)}
        else:
            return {"error": f"Tool '{function_name}' not found."}

    async def start(self):
        # Register self with the registry
        card = AgentCard(
            id=self.agent_id, name="Coordinator Agent", agent_type=AgentType.HOST,
            endpoint=f"http://{settings.a2a_host}:{settings.a2a_port}",
            capabilities=["orchestration"]
        )
        await registry.register_agent(card)

        # Use the base class start method for the server
        await super().start(host=settings.a2a_host, port=settings.a2a_port)

# To run this agent, use the main entry point at src/main.py