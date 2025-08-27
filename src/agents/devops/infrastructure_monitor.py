import asyncio
import psutil
import shutil
from typing import Dict, Any, List
from datetime import datetime
from utils.a2a_mock import A2AServer
from core.agent_registry import AgentCard, AgentType, registry


class InfrastructureMonitorAgent:
    def __init__(self):
        self.agent_id = "infra-monitor-001"
        self.agent_card = AgentCard(
            id=self.agent_id,
            name="Infrastructure Monitor",
            description="Monitors system resources, disk usage, and network connectivity",
            agent_type=AgentType.DEVOPS,
            capabilities=[
                "system_metrics",
                "disk_monitoring",
                "network_check",
                "resource_alerts"
            ],
            endpoint="http://localhost:8082",
            metadata={
                "version": "1.0.0",
                "author": "A2A Lab",
                "category": "infrastructure"
            }
        )
        
    async def start(self):
        await registry.register_agent(self.agent_card)
        server = A2AServer()
        
        @server.method("get_system_metrics")
        async def get_system_metrics() -> Dict[str, Any]:
            return await self._get_system_metrics()
        
        @server.method("check_disk_usage")
        async def check_disk_usage(path: str = "/") -> Dict[str, Any]:
            return await self._check_disk_usage(path)
        
        @server.method("get_network_status")
        async def get_network_status() -> Dict[str, Any]:
            return await self._get_network_status()
        
        @server.method("get_resource_alerts")
        async def get_resource_alerts() -> List[Dict[str, Any]]:
            return await self._get_resource_alerts()
        
        await server.start(host="0.0.0.0", port=8082)
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "usage_percent": cpu_percent,
                "core_count": psutil.cpu_count(),
                "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100
            }
        }
    
    async def _check_disk_usage(self, path: str) -> Dict[str, Any]:
        try:
            disk_usage = shutil.disk_usage(path)
            total, used, free = disk_usage
            
            return {
                "path": path,
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "used_percent": (used / total) * 100,
                "free_percent": (free / total) * 100,
                "status": "critical" if (used / total) > 0.9 else "warning" if (used / total) > 0.8 else "ok"
            }
        except Exception as e:
            return {
                "path": path,
                "error": str(e),
                "status": "error"
            }
    
    async def _get_network_status(self) -> Dict[str, Any]:
        net_io = psutil.net_io_counters()
        connections = psutil.net_connections()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "io_counters": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            },
            "active_connections": len([conn for conn in connections if conn.status == "ESTABLISHED"]),
            "listening_ports": len([conn for conn in connections if conn.status == "LISTEN"])
        }
    
    async def _get_resource_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        
        # CPU alert
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 80:
            alerts.append({
                "type": "cpu_high",
                "severity": "critical" if cpu_percent > 90 else "warning",
                "message": f"CPU usage is {cpu_percent:.1f}%",
                "value": cpu_percent,
                "threshold": 80,
                "timestamp": datetime.now().isoformat()
            })
        
        # Memory alert
        memory = psutil.virtual_memory()
        if memory.percent > 80:
            alerts.append({
                "type": "memory_high",
                "severity": "critical" if memory.percent > 90 else "warning",
                "message": f"Memory usage is {memory.percent:.1f}%",
                "value": memory.percent,
                "threshold": 80,
                "timestamp": datetime.now().isoformat()
            })
        
        # Disk alert
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > 80:
            alerts.append({
                "type": "disk_high",
                "severity": "critical" if disk_percent > 90 else "warning",
                "message": f"Disk usage is {disk_percent:.1f}%",
                "value": disk_percent,
                "threshold": 80,
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts


if __name__ == "__main__":
    agent = InfrastructureMonitorAgent()
    asyncio.run(agent.start())