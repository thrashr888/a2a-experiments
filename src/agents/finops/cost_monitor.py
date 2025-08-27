import asyncio
import psutil
import docker
from typing import Dict, Any, List
from datetime import datetime, timedelta
from utils.a2a_mock import A2AServer
from core.agent_registry import AgentCard, AgentType, registry


class CostMonitorAgent:
    def __init__(self):
        self.agent_id = "cost-monitor-001"
        self.agent_card = AgentCard(
            id=self.agent_id,
            name="Cost Monitor",
            description="Tracks resource usage costs and provides optimization recommendations",
            agent_type=AgentType.FINOPS,
            capabilities=[
                "resource_cost_tracking",
                "container_cost_analysis",
                "optimization_recommendations",
                "budget_alerts"
            ],
            endpoint="http://localhost:8084",
            metadata={
                "version": "1.0.0",
                "author": "A2A Lab",
                "category": "finops"
            }
        )
        
        # Cost parameters (adjustable based on actual costs)
        self.cost_rates = {
            "cpu_hour": 0.02,      # $0.02 per CPU hour
            "memory_gb_hour": 0.01, # $0.01 per GB memory hour
            "disk_gb_month": 0.10,  # $0.10 per GB disk per month
            "network_gb": 0.05,     # $0.05 per GB network transfer
            "power_kwh": 0.12       # $0.12 per kWh
        }
        
    async def start(self):
        await registry.register_agent(self.agent_card)
        server = A2AServer()
        
        @server.method("get_resource_costs")
        async def get_resource_costs(period_hours: int = 24) -> Dict[str, Any]:
            return await self._get_resource_costs(period_hours)
        
        @server.method("analyze_container_costs")
        async def analyze_container_costs() -> List[Dict[str, Any]]:
            return await self._analyze_container_costs()
        
        @server.method("get_optimization_recommendations")
        async def get_optimization_recommendations() -> List[Dict[str, Any]]:
            return await self._get_optimization_recommendations()
        
        @server.method("calculate_monthly_projection")
        async def calculate_monthly_projection() -> Dict[str, Any]:
            return await self._calculate_monthly_projection()
        
        await server.start(host="0.0.0.0", port=8084)
    
    async def _get_resource_costs(self, period_hours: int) -> Dict[str, Any]:
        # Get current system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        # Calculate costs for the period
        cpu_cores = psutil.cpu_count()
        memory_gb = memory.total / (1024**3)
        disk_gb = disk.total / (1024**3)
        
        # Estimated usage during period (simplified)
        cpu_cost = (cpu_percent / 100) * cpu_cores * period_hours * self.cost_rates["cpu_hour"]
        memory_cost = (memory.percent / 100) * memory_gb * period_hours * self.cost_rates["memory_gb_hour"]
        disk_cost = disk_gb * (period_hours / 24 / 30) * self.cost_rates["disk_gb_month"]
        
        # Network cost (simplified - using total bytes as proxy)
        network_gb = (network.bytes_sent + network.bytes_recv) / (1024**3)
        network_cost = network_gb * self.cost_rates["network_gb"]
        
        # Power consumption estimate (very rough)
        estimated_power_usage = (cpu_percent / 100) * 0.1  # 0.1 kW estimated for CPU
        power_cost = estimated_power_usage * period_hours * self.cost_rates["power_kwh"]
        
        total_cost = cpu_cost + memory_cost + disk_cost + network_cost + power_cost
        
        return {
            "period_hours": period_hours,
            "cost_breakdown": {
                "cpu_cost": round(cpu_cost, 4),
                "memory_cost": round(memory_cost, 4),
                "disk_cost": round(disk_cost, 4),
                "network_cost": round(network_cost, 4),
                "power_cost": round(power_cost, 4)
            },
            "total_cost": round(total_cost, 4),
            "resource_utilization": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "network_gb": round(network_gb, 3)
            },
            "cost_rates_used": self.cost_rates,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _analyze_container_costs(self) -> List[Dict[str, Any]]:
        container_costs = []
        
        try:
            client = docker.from_env()
            containers = client.containers.list(all=True)
            
            for container in containers:
                stats = container.stats(stream=False) if container.status == 'running' else None
                
                if stats and 'cpu_stats' in stats:
                    # Calculate container resource usage
                    cpu_usage = self._calculate_cpu_percentage(stats)
                    memory_usage_mb = stats['memory_stats'].get('usage', 0) / (1024**2)
                    memory_usage_gb = memory_usage_mb / 1024
                    
                    # Estimate costs (per hour)
                    cpu_cost_per_hour = (cpu_usage / 100) * self.cost_rates["cpu_hour"]
                    memory_cost_per_hour = memory_usage_gb * self.cost_rates["memory_gb_hour"]
                    
                    container_costs.append({
                        "container_id": container.id[:12],
                        "container_name": container.name,
                        "status": container.status,
                        "image": container.image.tags[0] if container.image.tags else "unknown",
                        "cpu_usage_percent": round(cpu_usage, 2),
                        "memory_usage_mb": round(memory_usage_mb, 2),
                        "estimated_hourly_cost": round(cpu_cost_per_hour + memory_cost_per_hour, 4),
                        "cost_breakdown": {
                            "cpu_hourly": round(cpu_cost_per_hour, 4),
                            "memory_hourly": round(memory_cost_per_hour, 4)
                        }
                    })
                else:
                    container_costs.append({
                        "container_id": container.id[:12],
                        "container_name": container.name,
                        "status": container.status,
                        "image": container.image.tags[0] if container.image.tags else "unknown",
                        "estimated_hourly_cost": 0.0,
                        "note": "Container not running or stats unavailable"
                    })
                    
        except Exception as e:
            container_costs.append({
                "status": "docker_unavailable",
                "message": "Docker access not available from container",
                "note": "Container analysis requires Docker socket access",
                "error_details": str(e),
                "timestamp": datetime.now().isoformat()
            })
        
        return container_costs
    
    def _calculate_cpu_percentage(self, stats: Dict) -> float:
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            if system_delta > 0:
                percpu_usage = stats['cpu_stats']['cpu_usage'].get('percpu_usage', [0])
                cpu_count = len(percpu_usage) if percpu_usage else 1
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100
                return cpu_percent
        except (KeyError, TypeError, ZeroDivisionError):
            pass
        return 0.0
    
    async def _get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        recommendations = []
        
        # Analyze system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # CPU optimization
        if cpu_percent < 20:
            recommendations.append({
                "type": "cpu_underutilization",
                "priority": "medium",
                "current_usage": f"{cpu_percent:.1f}%",
                "recommendation": "CPU usage is very low. Consider downsizing instance or consolidating workloads.",
                "potential_savings": "$10-30/month",
                "action": "Review workload requirements and consider smaller instance types"
            })
        elif cpu_percent > 80:
            recommendations.append({
                "type": "cpu_optimization",
                "priority": "high",
                "current_usage": f"{cpu_percent:.1f}%",
                "recommendation": "High CPU usage detected. Consider upgrading instance or optimizing workloads.",
                "potential_cost": "$15-50/month increase",
                "action": "Monitor performance and consider vertical scaling"
            })
        
        # Memory optimization
        if memory.percent < 30:
            recommendations.append({
                "type": "memory_underutilization",
                "priority": "low",
                "current_usage": f"{memory.percent:.1f}%",
                "recommendation": "Memory usage is low. Consider instances with less memory.",
                "potential_savings": "$5-20/month",
                "action": "Evaluate memory requirements and consider downsizing"
            })
        elif memory.percent > 85:
            recommendations.append({
                "type": "memory_optimization",
                "priority": "high",
                "current_usage": f"{memory.percent:.1f}%",
                "recommendation": "Memory usage is high. Consider adding memory or optimizing applications.",
                "potential_cost": "$10-40/month increase",
                "action": "Monitor memory leaks and consider memory optimization"
            })
        
        # Disk optimization
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > 80:
            recommendations.append({
                "type": "disk_cleanup",
                "priority": "medium",
                "current_usage": f"{disk_percent:.1f}%",
                "recommendation": "Disk usage is high. Clean up old files and logs.",
                "potential_savings": "$2-10/month",
                "action": "Implement log rotation and cleanup old data"
            })
        
        # Container optimization
        try:
            container_costs = await self._analyze_container_costs()
            total_container_cost = sum(
                c.get('estimated_hourly_cost', 0) for c in container_costs
                if isinstance(c.get('estimated_hourly_cost'), (int, float))
            )
            
            if total_container_cost > 1.0:  # More than $1/hour
                stopped_containers = [c for c in container_costs if c.get('status') != 'running']
                if stopped_containers:
                    recommendations.append({
                        "type": "container_cleanup",
                        "priority": "low",
                        "current_cost": f"${total_container_cost:.2f}/hour",
                        "recommendation": f"Remove {len(stopped_containers)} stopped containers to save storage.",
                        "potential_savings": "$1-5/month",
                        "action": "Clean up unused containers and images"
                    })
        except:
            pass
        
        return recommendations
    
    async def _calculate_monthly_projection(self) -> Dict[str, Any]:
        # Get current 24-hour costs
        daily_costs = await self._get_resource_costs(24)
        daily_total = daily_costs["total_cost"]
        
        # Project to monthly
        monthly_projection = daily_total * 30
        
        # Calculate trends (simplified)
        weekly_projection = daily_total * 7
        
        return {
            "current_daily_cost": round(daily_total, 2),
            "weekly_projection": round(weekly_projection, 2),
            "monthly_projection": round(monthly_projection, 2),
            "annual_projection": round(monthly_projection * 12, 2),
            "cost_breakdown_monthly": {
                "cpu": round(daily_costs["cost_breakdown"]["cpu_cost"] * 30, 2),
                "memory": round(daily_costs["cost_breakdown"]["memory_cost"] * 30, 2),
                "disk": round(daily_costs["cost_breakdown"]["disk_cost"] * 30, 2),
                "network": round(daily_costs["cost_breakdown"]["network_cost"] * 30, 2),
                "power": round(daily_costs["cost_breakdown"]["power_cost"] * 30, 2)
            },
            "budget_recommendations": {
                "conservative": round(monthly_projection * 1.2, 2),
                "moderate": round(monthly_projection * 1.5, 2),
                "aggressive_growth": round(monthly_projection * 2.0, 2)
            },
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    agent = CostMonitorAgent()
    asyncio.run(agent.start())