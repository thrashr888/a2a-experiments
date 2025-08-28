import asyncio
import json
import psutil
import shutil
from typing import Dict, Any, List
from datetime import datetime

from core.agent import AIAgent, AgentTool, A2AMessage
from utils.a2a_mock import A2AServer
from core.config import settings

DEVOPS_SYSTEM_PROMPT = """
You are Alex, a senior DevOps engineer with 10 years of experience in infrastructure management. 

Your expertise includes:
- System monitoring and alerting
- Infrastructure automation  
- Performance optimization
- Capacity planning
- Incident response

Your personality: Methodical, detail-oriented, proactive about preventing issues.
"""

devops_tools = [
    AgentTool(
        name="get_system_metrics",
        description="Get current system resource utilization (CPU, memory, disk).",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="get_resource_alerts",
        description="Check for any resource utilization alerts (CPU, memory, disk > 80%).",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="check_disk_usage",
        description="Check the disk usage for a specific path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file path to check."}
            },
            "required": ["path"],
        },
    ),
]


class DevOpsAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="devops-agent-alex-001",
            system_prompt=DEVOPS_SYSTEM_PROMPT,
            tools=devops_tools,
        )

    async def _execute_tool(self, tool_call, conversation_id: str) -> Dict[str, Any]:
        function_name = tool_call.function.name
        kwargs = json.loads(tool_call.function.arguments)
        print(f"Executing tool: {function_name} with args: {kwargs}")

        if function_name == "get_system_metrics":
            return await self._get_system_metrics()
        elif function_name == "get_resource_alerts":
            return await self._get_resource_alerts()
        elif function_name == "check_disk_usage":
            return await self._check_disk_usage(**kwargs)
        else:
            return {"error": f"Tool '{function_name}' not found."}

    async def _get_system_metrics(self) -> Dict[str, Any]:
        # Implementation from original InfrastructureMonitorAgent
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
        }

    async def _get_resource_alerts(self) -> List[Dict[str, Any]]:
        # Implementation from original InfrastructureMonitorAgent
        alerts = []
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 80:
            alerts.append(
                {"type": "cpu_high", "value": cpu_percent, "severity": "warning"}
            )
        memory = psutil.virtual_memory()
        if memory.percent > 80:
            alerts.append(
                {"type": "memory_high", "value": memory.percent, "severity": "warning"}
            )
        disk = psutil.disk_usage("/")
        if disk.percent > 80:
            alerts.append(
                {"type": "disk_high", "value": disk.percent, "severity": "warning"}
            )
        return alerts

    async def _check_disk_usage(self, path: str) -> Dict[str, Any]:
        # Implementation from original InfrastructureMonitorAgent
        try:
            disk_usage = shutil.disk_usage(path)
            return {
                "path": path,
                "total_bytes": disk_usage.total,
                "used_bytes": disk_usage.used,
                "used_percent": (disk_usage.used / disk_usage.total) * 100,
            }
        except FileNotFoundError:
            return {
                "path": path,
                "error": f"Path '{path}' not found or not accessible in containerized environment",
                "suggestion": "Use '/' for root filesystem or '/app' for application directory",
            }

    async def start(self):
        await super().start(host="0.0.0.0", port=8082)


# To run this agent, use the main entry point at src/main.py
