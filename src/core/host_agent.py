import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils.a2a_mock import A2AServer, A2AClient
from .agent_registry import AgentCard, AgentType, AgentStatus, registry
from .config import settings


class HostAgent:
    def __init__(self):
        self.agent_id = "host-agent-001"
        self.agent_card = AgentCard(
            id=self.agent_id,
            name="Host Agent",
            description="Main orchestrator agent that coordinates interactions between specialized agents",
            agent_type=AgentType.HOST,
            capabilities=[
                "agent_discovery",
                "workflow_orchestration",
                "multi_agent_coordination",
                "system_status"
            ],
            endpoint=f"http://{settings.a2a_host}:{settings.a2a_port}",
            metadata={
                "version": "1.0.0",
                "author": "A2A Lab",
                "category": "orchestration"
            }
        )
        
    async def start(self):
        await registry.register_agent(self.agent_card)
        server = A2AServer()
        
        @server.method("orchestrate_security_check")
        async def orchestrate_security_check() -> Dict[str, Any]:
            return await self._orchestrate_security_check()
        
        @server.method("orchestrate_resource_optimization")
        async def orchestrate_resource_optimization() -> Dict[str, Any]:
            return await self._orchestrate_resource_optimization()
        
        @server.method("get_system_overview")
        async def get_system_overview() -> Dict[str, Any]:
            return await self._get_system_overview()
        
        @server.method("orchestrate_cost_analysis")
        async def orchestrate_cost_analysis() -> Dict[str, Any]:
            return await self._orchestrate_cost_analysis()
        
        @server.method("list_available_agents")
        async def list_available_agents() -> List[Dict[str, Any]]:
            agents = await registry.list_agents()
            return [agent.to_dict() for agent in agents]
        
        await server.start(host=settings.a2a_host, port=settings.a2a_port)
    
    async def _orchestrate_security_check(self) -> Dict[str, Any]:
        results = {
            "workflow": "security_check",
            "timestamp": datetime.now().isoformat(),
            "results": {},
            "summary": {}
        }
        
        # Find security agents
        security_agents = await registry.find_agents_by_capability("security_alerts")
        if not security_agents:
            results["error"] = "No security agents available"
            return results
        
        for agent in security_agents:
            try:
                client = A2AClient(agent.endpoint)
                
                # Get security alerts from each agent
                if agent.id == "security-monitor-001":
                    alerts = await client.call("get_security_alerts")
                    results["results"][agent.name] = {
                        "status": "success",
                        "alerts": alerts,
                        "agent_id": agent.id
                    }
                
            except Exception as e:
                results["results"][agent.name] = {
                    "status": "error",
                    "error": str(e),
                    "agent_id": agent.id
                }
        
        # Aggregate results
        all_alerts = []
        for agent_name, result in results["results"].items():
            if result["status"] == "success" and "alerts" in result:
                all_alerts.extend(result["alerts"])
        
        results["summary"] = {
            "total_agents_checked": len(security_agents),
            "total_alerts": len(all_alerts),
            "high_severity_alerts": len([a for a in all_alerts if a.get("severity") == "high"]),
            "medium_severity_alerts": len([a for a in all_alerts if a.get("severity") == "medium"]),
            "low_severity_alerts": len([a for a in all_alerts if a.get("severity") == "low"])
        }
        
        return results
    
    async def _orchestrate_resource_optimization(self) -> Dict[str, Any]:
        results = {
            "workflow": "resource_optimization",
            "timestamp": datetime.now().isoformat(),
            "results": {},
            "recommendations": []
        }
        
        # Get infrastructure metrics
        infra_agents = await registry.find_agents_by_capability("system_metrics")
        for agent in infra_agents:
            try:
                client = A2AClient(agent.endpoint)
                metrics = await client.call("get_system_metrics")
                alerts = await client.call("get_resource_alerts")
                
                results["results"][agent.name] = {
                    "status": "success",
                    "metrics": metrics,
                    "alerts": alerts,
                    "agent_id": agent.id
                }
            except Exception as e:
                results["results"][agent.name] = {
                    "status": "error",
                    "error": str(e),
                    "agent_id": agent.id
                }
        
        # Get cost optimization recommendations
        finops_agents = await registry.find_agents_by_capability("optimization_recommendations")
        for agent in finops_agents:
            try:
                client = A2AClient(agent.endpoint)
                recommendations = await client.call("get_optimization_recommendations")
                
                results["results"][agent.name] = {
                    "status": "success",
                    "recommendations": recommendations,
                    "agent_id": agent.id
                }
                
                results["recommendations"].extend(recommendations)
                
            except Exception as e:
                results["results"][agent.name] = {
                    "status": "error",
                    "error": str(e),
                    "agent_id": agent.id
                }
        
        return results
    
    async def _get_system_overview(self) -> Dict[str, Any]:
        overview = {
            "timestamp": datetime.now().isoformat(),
            "registry_status": await registry.get_registry_state(),
            "agent_health": {},
            "system_status": "healthy"
        }
        
        # Check health of all registered agents
        agents = await registry.list_agents(status=AgentStatus.ONLINE)
        
        for agent in agents:
            try:
                # Simple health check - try to connect to agent
                client = A2AClient(agent.endpoint)
                
                # Different health checks based on agent type
                if agent.agent_type == AgentType.DEVOPS:
                    if "system_metrics" in agent.capabilities:
                        result = await client.call("get_system_metrics")
                        overview["agent_health"][agent.id] = "healthy"
                elif agent.agent_type == AgentType.SECOPS:
                    if "security_alerts" in agent.capabilities:
                        result = await client.call("get_security_alerts")
                        overview["agent_health"][agent.id] = "healthy"
                elif agent.agent_type == AgentType.FINOPS:
                    if "resource_cost_tracking" in agent.capabilities:
                        result = await client.call("get_resource_costs")
                        overview["agent_health"][agent.id] = "healthy"
                else:
                    overview["agent_health"][agent.id] = "unknown"
                    
            except Exception as e:
                overview["agent_health"][agent.id] = f"unhealthy: {str(e)}"
                await registry.update_agent_status(agent.id, AgentStatus.ERROR)
        
        # Determine overall system health
        unhealthy_agents = [
            agent_id for agent_id, health in overview["agent_health"].items()
            if not health == "healthy"
        ]
        
        if len(unhealthy_agents) > len(agents) / 2:
            overview["system_status"] = "degraded"
        elif unhealthy_agents:
            overview["system_status"] = "warning"
        
        return overview
    
    async def _orchestrate_cost_analysis(self) -> Dict[str, Any]:
        analysis = {
            "workflow": "cost_analysis",
            "timestamp": datetime.now().isoformat(),
            "results": {},
            "summary": {}
        }
        
        # Get cost data from FinOps agents
        finops_agents = await registry.find_agents_by_capability("resource_cost_tracking")
        
        for agent in finops_agents:
            try:
                client = A2AClient(agent.endpoint)
                
                # Get various cost metrics
                resource_costs = await client.call("get_resource_costs", period_hours=24)
                container_costs = await client.call("analyze_container_costs")
                monthly_projection = await client.call("calculate_monthly_projection")
                recommendations = await client.call("get_optimization_recommendations")
                
                analysis["results"][agent.name] = {
                    "status": "success",
                    "resource_costs": resource_costs,
                    "container_costs": container_costs,
                    "monthly_projection": monthly_projection,
                    "recommendations": recommendations,
                    "agent_id": agent.id
                }
                
            except Exception as e:
                analysis["results"][agent.name] = {
                    "status": "error",
                    "error": str(e),
                    "agent_id": agent.id
                }
        
        # Create summary
        if analysis["results"]:
            successful_results = [
                result for result in analysis["results"].values()
                if result["status"] == "success"
            ]
            
            if successful_results:
                # Aggregate costs and recommendations
                total_daily_cost = sum(
                    result.get("resource_costs", {}).get("total_cost", 0)
                    for result in successful_results
                )
                
                all_recommendations = []
                for result in successful_results:
                    all_recommendations.extend(result.get("recommendations", []))
                
                analysis["summary"] = {
                    "total_daily_cost": round(total_daily_cost, 4),
                    "estimated_monthly_cost": round(total_daily_cost * 30, 2),
                    "total_recommendations": len(all_recommendations),
                    "high_priority_recommendations": len([
                        r for r in all_recommendations if r.get("priority") == "high"
                    ])
                }
        
        return analysis


if __name__ == "__main__":
    host = HostAgent()
    asyncio.run(host.start())