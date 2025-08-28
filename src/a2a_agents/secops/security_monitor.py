import asyncio
import json
import re
import os
import subprocess
from typing import Dict, Any, List
from datetime import datetime, timedelta

from core.agent import AIAgent, AgentTool, A2AMessage
from core.config import settings

SECOPS_SYSTEM_PROMPT = """
You are Jordan, a cybersecurity analyst with expertise in threat detection and incident response.

Your expertise includes:
- Security monitoring and analysis
- Threat hunting and detection
- Vulnerability assessment
- Security policy enforcement
- Incident investigation

Your personality: Vigilant, thorough, always thinking about potential threats.

When answering questions:
1. Always assess security implications
2. Look for indicators of compromise
3. Recommend defense-in-depth strategies
4. Prioritize by risk level
"""

secops_tools = [
    AgentTool(
        name="scan_failed_logins",
        description="Scan system logs for failed login attempts over a given period.",
        parameters={
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "The number of hours back to scan.",
                }
            },
            "required": ["hours"],
        },
    ),
    AgentTool(
        name="check_suspicious_processes",
        description="Check for running processes with names matching common hacking tools.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="scan_network_connections",
        description="Scan for active network connections and unusual listening ports.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="get_security_alerts",
        description="Get a summary of all security alerts based on various checks.",
        parameters={"type": "object", "properties": {}},
    ),
]


class SecOpsAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="secops-agent-jordan-001",
            system_prompt=SECOPS_SYSTEM_PROMPT,
            tools=secops_tools,
        )
        self.log_paths = ["/var/log/auth.log", "/var/log/secure"]

    async def _execute_tool(self, tool_call, conversation_id: str) -> Dict[str, Any]:
        function_name = tool_call.function.name
        kwargs = json.loads(tool_call.function.arguments)
        print(f"Executing tool: {function_name} with args: {kwargs}")

        if function_name == "scan_failed_logins":
            return await self._scan_failed_logins(**kwargs)
        elif function_name == "check_suspicious_processes":
            return await self._check_suspicious_processes()
        elif function_name == "scan_network_connections":
            return await self._scan_network_connections()
        elif function_name == "get_security_alerts":
            return await self._get_security_alerts()
        else:
            return {"error": f"Tool '{function_name}' not found."}

    async def _scan_failed_logins(self, hours: int) -> Dict[str, Any]:
        # Existing logic from the original agent
        failed_attempts = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        patterns = [
            r"Failed password for (\w+) from ([\d\.]+)",
            r"Invalid user (\w+) from ([\d\.]+)",
            r"authentication failure.*user=(\w+).*rhost=([\d\.]+)",
        ]
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
            try:
                with open(log_path, "r") as f:
                    # This is a simplified implementation for the lab
                    pass
            except Exception as e:
                continue
        # Mock data for demonstration
        return {
            "scan_period_hours": hours,
            "total_failed_attempts": 25,
            "unique_ips": 5,
            "summary": f"Found 25 failed login attempts from 5 unique IPs in the last {hours} hours.",
        }

    async def _check_suspicious_processes(self) -> List[Dict[str, Any]]:
        # Mock data for demonstration
        return [
            {
                "pid": "12345",
                "command": "nc -l -p 1337",
                "user": "root",
                "detected_pattern": "nc",
                "summary": "Found a netcat process listening on a high port, which is suspicious.",
            }
        ]

    async def _scan_network_connections(self) -> Dict[str, Any]:
        # Mock data for demonstration
        return {
            "total_listening_ports": 15,
            "unusual_listening_ports": [
                {"protocol": "tcp", "address": "0.0.0.0:1337", "port": "1337"}
            ],
            "summary": "Found 15 listening ports, one of which (1337) is unusual and associated with the suspicious netcat process.",
        }

    async def _get_security_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        if await self._check_suspicious_processes():
            alerts.append(
                {
                    "severity": "high",
                    "type": "suspicious_process",
                    "details": "Found netcat process",
                }
            )
        if (await self._scan_failed_logins(1))["total_failed_attempts"] > 10:
            alerts.append(
                {
                    "severity": "medium",
                    "type": "failed_logins",
                    "details": "High number of failed logins",
                }
            )
        return alerts

    async def start(self):
        await super().start(host="0.0.0.0", port=8083)
