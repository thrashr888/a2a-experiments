from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from core.agent_registry import registry, AgentCard, AgentType, AgentStatus
from web.routes import chat, api
from web.utils import templates

app = FastAPI(
    title="A2A Learning Lab",
    description="Multi-Agent System for DevOps, SecOps, and FinOps",
    version="1.0.0"
)

# Setup static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Include route modules
app.include_router(chat.router)
app.include_router(api.router)

# Initialize demo agents on startup
@app.on_event("startup")
async def startup_event():
    """Initialize demo agents in the registry"""
    
    # Add demo agents to registry
    demo_agents = [
        AgentCard(
            id="host-agent-001",
            name="Host Agent",
            description="Main orchestrator agent that coordinates interactions between specialized agents",
            agent_type=AgentType.HOST,
            capabilities=["agent_discovery", "workflow_orchestration", "multi_agent_coordination", "system_status"],
            endpoint="http://localhost:8081",
            status=AgentStatus.ONLINE
        ),
        AgentCard(
            id="devops-agent-alex-001",
            name="Infrastructure Monitor (Alex)",
            description="Monitors system resources, disk usage, and network connectivity",
            agent_type=AgentType.DEVOPS,
            capabilities=["system_monitoring", "performance_analysis", "resource_alerts", "infrastructure_management"],
            endpoint="http://localhost:8082",
            status=AgentStatus.ONLINE
        ),
        AgentCard(
            id="secops-agent-jordan-001", 
            name="Security Monitor (Jordan)",
            description="Monitors security threats, failed logins, and suspicious network activity",
            agent_type=AgentType.SECOPS,
            capabilities=["threat_detection", "security_monitoring", "incident_response", "vulnerability_assessment"],
            endpoint="http://localhost:8083",
            status=AgentStatus.ONLINE
        ),
        AgentCard(
            id="finops-agent-casey-001",
            name="Cost Monitor (Casey)",
            description="Tracks resource costs, provides optimization recommendations, and monitors spending",
            agent_type=AgentType.FINOPS,
            capabilities=["cost_analysis", "resource_optimization", "budget_tracking", "financial_reporting"],
            endpoint="http://localhost:8084",
            status=AgentStatus.ONLINE
        )
    ]
    
    for agent in demo_agents:
        await registry.register_agent(agent)
        
    print("Demo agents registered successfully")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}

# Main UI endpoint
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})