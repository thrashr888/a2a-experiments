from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path
from core.agent_registry import registry
from core.config import settings
from utils.a2a_mock import A2AClient
from datetime import datetime


app = FastAPI(
    title="A2A Learning Lab",
    description="Multi-Agent System for DevOps, SecOps, and FinOps",
    version="1.0.0"
)

# Setup static files and templates
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
templates_path = Path(__file__).parent / "templates"
templates_path.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}

# API endpoints
@app.get("/api/agents")
async def get_agents():
    agents = await registry.list_agents()
    return [agent.to_dict() for agent in agents]

@app.get("/api/registry-status")
async def get_registry_status():
    return await registry.get_registry_state()

@app.post("/api/orchestrate/{workflow}")
async def orchestrate_workflow(workflow: str):
    try:
        host_client = A2AClient(f"http://{settings.a2a_host}:{settings.a2a_port}")
        
        if workflow == "security-check":
            result = await host_client.call("orchestrate_security_check")
        elif workflow == "resource-optimization":
            result = await host_client.call("orchestrate_resource_optimization")
        elif workflow == "cost-analysis":
            result = await host_client.call("orchestrate_cost_analysis")
        elif workflow == "system-overview":
            result = await host_client.call("get_system_overview")
        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown workflow: {workflow}"}
            )
        
        return result
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/api/agent/{agent_id}/call/{method}")
async def call_agent_method(agent_id: str, method: str):
    try:
        agent = await registry.get_agent(agent_id)
        if not agent:
            return JSONResponse(
                status_code=404,
                content={"error": f"Agent {agent_id} not found"}
            )
        
        client = A2AClient(agent.endpoint)
        result = await client.call(method)
        return result
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# HTMX Component Endpoints

@app.get("/api/stats", response_class=HTMLResponse)
async def get_stats_component(request: Request):
    """Get stats grid component for HTMX"""
    try:
        registry_status = await registry.get_registry_state()
        total_agents = registry_status.get("total_agents", 0)
        online_agents = registry_status.get("agents_by_status", {}).get("online", 0)
        
        # System status logic
        if total_agents == 0:
            system_status = "🔴"
        elif online_agents == total_agents:
            system_status = "🟢"
        elif online_agents > total_agents / 2:
            system_status = "🟡"
        else:
            system_status = "🔴"
        
        return templates.TemplateResponse("components/stats.html", {
            "request": request,
            "total_agents": total_agents,
            "online_agents": online_agents,
            "workflows_run": 0,  # TODO: Track this in session/database
            "system_status": system_status
        })
    except Exception as e:
        return templates.TemplateResponse("components/stats.html", {
            "request": request,
            "total_agents": 0,
            "online_agents": 0,
            "workflows_run": 0,
            "system_status": "🔴"
        })

@app.get("/api/agents-grid", response_class=HTMLResponse)
async def get_agents_grid_component(request: Request):
    """Get agents grid component for HTMX"""
    try:
        agents = await registry.list_agents()
        return templates.TemplateResponse("components/agents_grid.html", {
            "request": request,
            "agents": [agent.to_dict() for agent in agents]
        })
    except Exception as e:
        return templates.TemplateResponse("components/agents_grid.html", {
            "request": request,
            "agents": []
        })

# Updated workflow endpoints to return HTML components
@app.post("/api/orchestrate/{workflow}", response_class=HTMLResponse)
async def orchestrate_workflow_component(request: Request, workflow: str):
    """Orchestrate workflow and return HTML component"""
    try:
        host_client = A2AClient(f"http://{settings.a2a_host}:{settings.a2a_port}")
        
        if workflow == "security-check":
            result = await host_client.call("orchestrate_security_check")
            return templates.TemplateResponse("components/security_results.html", {
                "request": request,
                "workflow": workflow,
                "result": result
            })
        elif workflow == "resource-optimization":
            result = await host_client.call("orchestrate_resource_optimization")
            return templates.TemplateResponse("components/optimization_results.html", {
                "request": request,
                "workflow": workflow,
                "result": result
            })
        elif workflow == "cost-analysis":
            result = await host_client.call("orchestrate_cost_analysis")
            return templates.TemplateResponse("components/cost_results.html", {
                "request": request,
                "workflow": workflow,
                "result": result
            })
        elif workflow == "system-overview":
            result = await host_client.call("get_system_overview")
            return templates.TemplateResponse("components/overview_results.html", {
                "request": request,
                "workflow": workflow,
                "result": result
            })
        else:
            return templates.TemplateResponse("components/error.html", {
                "request": request,
                "error": f"Unknown workflow: {workflow}"
            })
        
    except Exception as e:
        return templates.TemplateResponse("components/error.html", {
            "request": request,
            "error": str(e)
        })

# Main UI endpoint
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)