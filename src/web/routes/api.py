from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from core.agent_registry import registry, AgentStatus
from web.utils import safe_template_response
import asyncio

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/stats", response_class=HTMLResponse)
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

        context = {
            "total_agents": total_agents,
            "online_agents": online_agents,
            "workflows_run": 0,  # Future: Track conversation count in session storage
            "system_status": system_status,
        }
    except Exception:
        context = None

    fallback = {
        "total_agents": 0,
        "online_agents": 0,
        "workflows_run": 0,
        "system_status": "🔴",
    }

    return safe_template_response("components/stats.html", request, context, fallback)


@router.get("/agents-grid", response_class=HTMLResponse)
async def get_agents_grid_component(request: Request):
    """Get agents grid component for HTMX"""
    try:
        agents = await registry.list_agents()
        context = {"agents": [agent.to_dict() for agent in agents]}
    except Exception:
        context = None

    fallback = {"agents": []}
    return safe_template_response(
        "components/agents_grid.html", request, context, fallback
    )
