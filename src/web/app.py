from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from web.routes import chat, api
from web.utils import templates

app = FastAPI(
    title="A2A Learning Lab",
    description="Multi-Agent System for DevOps, SecOps, and FinOps",
    version="1.0.0",
)

# Setup static files
static_path = Path(__file__).parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Include route modules
app.include_router(chat.router)
app.include_router(api.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}


# Main UI endpoint
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
