"""Shared utilities for web routes"""

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown
from markupsafe import Markup

# Shared template instance 
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Add markdown filter to templates
def markdown_filter(text):
    """Convert markdown text to HTML"""
    if not text:
        return ""
    # Configure markdown with safe extensions
    md = markdown.Markdown(extensions=['nl2br', 'fenced_code', 'tables'])
    return Markup(md.convert(text))

templates.env.filters['markdown'] = markdown_filter

def safe_template_response(
    template_name: str,
    request: Request,
    context: dict = None,
    fallback_context: dict = None
) -> HTMLResponse:
    """Safely render template with fallback error handling"""
    try:
        final_context = {"request": request}
        if context:
            final_context.update(context)
        return templates.TemplateResponse(template_name, final_context)
    except Exception:
        # Use fallback context on error
        fallback = {"request": request}
        if fallback_context:
            fallback.update(fallback_context)
        return templates.TemplateResponse(template_name, fallback)