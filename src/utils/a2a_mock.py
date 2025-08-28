"""Mock A2A server/client for testing agent communication.

Provides a lightweight FastAPI-based server (`A2AServer`) and a minimal async
HTTP client (`A2AClient`) that posts JSON payloads to an agent's `/process`
endpoint. This is intended only for local testing and examples.
"""

import asyncio
from typing import Dict, Any, Callable
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn


class A2AServer:
    """Mock A2A server implementation using FastAPI"""

    def __init__(self, agent=None):
        self.app = FastAPI()
        self.agent = agent
        self.methods: Dict[str, Callable] = {}

    def method(self, name: str):
        """Decorator to register method handlers"""

        def decorator(func):
            self.methods[name] = func
            return func

        return decorator

    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the server"""

        @self.app.post("/process")
        async def process_request(request: Request):
            try:
                data = await request.json()

                # If we have a "process" method registered, use it
                if "process" in self.methods:
                    result = await self.methods["process"](data)
                    return JSONResponse(content=result)
                else:
                    return JSONResponse(
                        content={"error": "No process method registered"},
                        status_code=500,
                    )

            except Exception as e:
                print(f"A2A Mock Server Error: {e}")
                print(f"Error type: {type(e)}")
                import traceback

                traceback.print_exc()
                return JSONResponse(content={"error": str(e)}, status_code=500)

        print(f"🚀 Starting A2A Mock Server on {host}:{port}")
        config = uvicorn.Config(app=self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


class A2AClient:
    """Minimal async client for calling mock A2A agents."""

    def __init__(self, base_url: str):
        # e.g., "http://localhost:8082"
        self.base_url = base_url.rstrip("/")

    async def call(
        self, method: str, params: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Call an agent method by POSTing to `/process`.

        Payload format is `{ "method": <str>, "params": <dict> }`.
        Returns parsed JSON response or an error dict on failure.
        """
        try:
            import httpx

            payload: Dict[str, Any] = {"method": method}
            if params:
                payload["params"] = params

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/process", json=payload, timeout=30.0
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}
