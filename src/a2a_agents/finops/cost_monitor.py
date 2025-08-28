import asyncio
import json
import psutil
from typing import Dict, Any, List

from core.agent import AIAgent, AgentTool, A2AMessage
from core.config import settings

FINOPS_SYSTEM_PROMPT = """
You are Casey, a FinOps engineer focused on cloud cost optimization and financial accountability.

Your expertise includes:
- Cost monitoring and analysis
- Resource optimization
- Budget planning and forecasting
- Chargeback and showback
- Cost anomaly detection

Your personality: Data-driven, business-focused, always looking for savings opportunities.

When answering questions:
1. Always consider cost implications
2. Provide ROI calculations when relevant
3. Suggest both immediate and strategic optimizations
4. Balance performance with cost
"""

finops_tools = [
    AgentTool(
        name="get_resource_costs",
        description="Get a breakdown of current resource costs (CPU, memory, disk).",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="get_optimization_recommendations",
        description="Get a list of actionable recommendations for cost savings.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="calculate_monthly_projection",
        description="Calculate the projected monthly cost based on current usage.",
        parameters={"type": "object", "properties": {}},
    ),
]


class FinOpsAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="finops-agent-casey-001",
            system_prompt=FINOPS_SYSTEM_PROMPT,
            tools=finops_tools,
        )
        self.cost_rates = {"cpu_hour": 0.02, "memory_gb_hour": 0.01}

    async def _execute_tool(self, tool_call, conversation_id: str, user_auth_token: str = None) -> Dict[str, Any]:
        function_name = tool_call.function.name
        kwargs = json.loads(tool_call.function.arguments)
        print(f"Executing tool: {function_name} with args: {kwargs}")

        if function_name == "get_resource_costs":
            return await self._get_resource_costs()
        elif function_name == "get_optimization_recommendations":
            return await self._get_optimization_recommendations()
        elif function_name == "calculate_monthly_projection":
            return await self._calculate_monthly_projection()
        else:
            return {"error": f"Tool '{function_name}' not found."}

    async def _get_resource_costs(self) -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        cpu_cost = (
            (cpu_percent / 100) * psutil.cpu_count() * self.cost_rates["cpu_hour"]
        )
        memory_cost = (
            (memory.percent / 100)
            * (memory.total / 1024**3)
            * self.cost_rates["memory_gb_hour"]
        )
        return {
            "cpu_cost_per_hour": round(cpu_cost, 4),
            "memory_cost_per_hour": round(memory_cost, 4),
            "total_cost_per_hour": round(cpu_cost + memory_cost, 4),
            "summary": f"Current hourly cost is estimated at ${round(cpu_cost + memory_cost, 4)}.",
        }

    async def _get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        cpu_percent = psutil.cpu_percent(interval=None)
        recommendations = []
        if cpu_percent < 10:
            recommendations.append(
                {
                    "priority": "medium",
                    "recommendation": "CPU utilization is very low. Consider downsizing the instance to save costs.",
                    "potential_savings": "$10-30/month",
                }
            )
        return recommendations

    async def _calculate_monthly_projection(self) -> Dict[str, Any]:
        costs = await self._get_resource_costs()
        monthly_projection = costs["total_cost_per_hour"] * 24 * 30
        return {
            "projected_monthly_cost": round(monthly_projection, 2),
            "summary": f"Based on current usage, the projected monthly cost is ${round(monthly_projection, 2)}.",
        }

    async def start(self):
        await super().start(host="0.0.0.0", port=8084)
